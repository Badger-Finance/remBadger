import brownie
from brownie import RemBadger, chain
from helpers.constants import AddressZero
from rich.console import Console
from helpers.utils import approx

C = Console()

WHITELISTED_AMOUNT = 1788000000000000000000  # 1788 BADGER


def test_rembadger_amendment_upgrade(
    rembadger,
    badger,
    proxy_admin,
    proxy_admin_gov,
    whitelisted_user,
    random,
    devMultisig,
):
    """
    The following test case is a simulation of the upgrade process for the RemBadger contract and the
    execution of the operations required to successfully allow for the re-entry of the whitelisted user.
    Note: All the transactions can be executed atomically by governance, given that the whitelisted user 
    transfers the required amount of BADGER to the governance address.

    Atomic operation:
    1. Execute the upgrade to the new implementation
    2. Open deposits for governance only
    3. Governance approves the deposit amount to remBADGER
    4. Governance calls depositFor the whitelisted user
    5. Governance bricks deposits
    """

    # Assert current conditions before upgrade
    assert rembadger.depositsEnded() == True
    assert rembadger.balanceOf(whitelisted_user.address) == 0
    assert rembadger.guestList() == AddressZero
    assert assert_blocked_deposit(rembadger, random, "No longer accepting Deposits")
    assert assert_blocked_deposit(
        rembadger, whitelisted_user, "No longer accepting Deposits"
    )

    # Deploy and upgrade to the new implementation
    prev_available = rembadger.available()
    prev_gov = rembadger.governance()
    prev_keeper = rembadger.keeper()
    prev_token = rembadger.token()
    prev_controller = rembadger.controller()
    prev_balance = rembadger.balance()
    prev_min = rembadger.min()
    prev_max = rembadger.max()
    prev_getPricePerFullShare = rembadger.getPricePerFullShare()

    new_logic = RemBadger.deploy({"from": devMultisig})

    # Deploy new logic
    proxy_admin.upgrade(rembadger, new_logic, {"from": proxy_admin_gov})

    ## Checking all variables are as expected
    assert prev_available == rembadger.available()
    assert prev_gov == rembadger.governance()
    assert prev_keeper == rembadger.keeper()
    assert prev_token == rembadger.token()
    assert prev_controller == rembadger.controller()
    assert prev_balance == rembadger.balance()
    assert prev_min == rembadger.min()
    assert prev_max == rembadger.max()
    assert prev_getPricePerFullShare == rembadger.getPricePerFullShare()

    # Open deposits again for governance only
    rembadger.enableDeposits({"from": devMultisig})
    assert rembadger.depositsEnded() == False
    assert assert_blocked_deposit(
        rembadger, random, "onlyGovernance"
    )  # Random user still blocked
    assert assert_blocked_deposit(
        rembadger, whitelisted_user, "onlyGovernance"
    )

    # User transfers the amount of BADGER to deposit to governance
    badger.transfer(devMultisig, WHITELISTED_AMOUNT, {"from": whitelisted_user})
    assert badger.balanceOf(devMultisig) >= WHITELISTED_AMOUNT

    # Governance deposits for user
    assert rembadger.balanceOf(whitelisted_user.address) == 0
    badger.approve(rembadger, WHITELISTED_AMOUNT, {"from": devMultisig})
    rembadger.depositFor(whitelisted_user.address, WHITELISTED_AMOUNT, {"from": devMultisig})
    C.print(
        f"User balance: {rembadger.balanceOf(whitelisted_user.address)/1e18} remBADGER"
    )
    assert prev_balance + WHITELISTED_AMOUNT == rembadger.balance()
    assert (
        prev_getPricePerFullShare == rembadger.getPricePerFullShare()
    )  # PPFS do not increase with deposits
    assert approx(
        rembadger.balanceOf(whitelisted_user.address),
        (WHITELISTED_AMOUNT * 1e18) / prev_getPricePerFullShare,
        0.1,
    )

    # Governance bricks deposit to restore final state
    rembadger.brickDeposits({"from": devMultisig})
    assert rembadger.depositsEnded() == True
    assert assert_blocked_deposit(rembadger, random, "No longer accepting Deposits")
    assert assert_blocked_deposit(
        rembadger, whitelisted_user, "No longer accepting Deposits"
    )

    chain.snapshot()
    # User withdraws and recovers its original BADGER (no more since emissions ended)
    prev_balance = badger.balanceOf(whitelisted_user.address)
    rembadger.withdrawAll({"from": whitelisted_user})
    after_balance = badger.balanceOf(whitelisted_user.address)
    withdrawn = after_balance - prev_balance
    assert approx(withdrawn, WHITELISTED_AMOUNT, 0.1)
    C.print(f"User balance withdrawn: {withdrawn/1e18} BADGER")
    chain.revert()


def assert_blocked_deposit(rembadger, user, revert_message):
    # Attempt a random deposit
    with brownie.reverts(revert_message):
        rembadger.deposit(1e18, {"from": user})

    return True
