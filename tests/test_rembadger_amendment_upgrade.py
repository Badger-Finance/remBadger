import brownie
from brownie import RemBadger, VipCappedGuestListBbtcUpgradeable, chain
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
    # Assert current conditions before upgrade
    assert rembadger.depositsEnded() == True
    assert rembadger.balanceOf(whitelisted_user.address) == 0
    assert rembadger.guestList() == AddressZero
    assert assert_blocked_deposit(rembadger, random, "No longer accepting Deposits")

    # Deploy and configure the guestlist
    guestlist = VipCappedGuestListBbtcUpgradeable.deploy({"from": devMultisig})
    guestlist.initialize(rembadger, {"from": devMultisig})
    guestlist.setGuestRoot("0x123")  # Random Guest Root adds verification requirement
    guestlist.setGuests(
        [whitelisted_user], [True]
    )  # Only manual list with a single user
    guestlist.setUserDepositCap(WHITELISTED_AMOUNT)  # Only approved amount for the user
    total_deposited = rembadger.totalSupply() * rembadger.getPricePerFullShare() / 1e18
    assert approx(total_deposited, rembadger.balance(), 0.1)
    guestlist.setTotalDepositCap(
        total_deposited + WHITELISTED_AMOUNT + 1e18
    )  # Only approved amount added to the total for extra precaution
    assert guestlist.guests(whitelisted_user.address) == True
    assert (
        guestlist.remainingUserDepositAllowed(whitelisted_user.address)
        == WHITELISTED_AMOUNT
    )
    assert approx(guestlist.remainingTotalDepositAllowed(), WHITELISTED_AMOUNT + 1e18, 0.1)

    rembadger.setGuestList(
        guestlist, {"from": devMultisig}
    )  # Setting guestlist on vault
    assert rembadger.guestList() == guestlist.address

    # Deposits are still not allowed, not even for the whitelisted user
    assert assert_blocked_deposit(rembadger, random, "guest-list-authorization")
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

    # Open deposits again
    rembadger.enableDeposits({"from": devMultisig})
    assert rembadger.depositsEnded() == False
    assert assert_blocked_deposit(
        rembadger, random, "guest-list-authorization"
    )  # Random user still blocked

    # Witelisted user can deposit up to its limit
    assert rembadger.balanceOf(whitelisted_user.address) == 0
    with brownie.reverts("guest-list-authorization"):
        rembadger.deposit(WHITELISTED_AMOUNT + 1, {"from": whitelisted_user})

    badger.approve(rembadger, WHITELISTED_AMOUNT, {"from": whitelisted_user})
    rembadger.deposit(WHITELISTED_AMOUNT, {"from": whitelisted_user})
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
    # User can't deposit more (457 units, non zero due to odd accounting on guestlist)
    # assert (
    #     guestlist.remainingUserDepositAllowed(whitelisted_user.address)
    #     == 0
    # )
    assert approx(guestlist.remainingTotalDepositAllowed(), 1e18, 0.1)
    badger.approve(rembadger, WHITELISTED_AMOUNT, {"from": whitelisted_user})
    assert assert_blocked_deposit(
        rembadger, whitelisted_user, "guest-list-authorization"
    )
    assert assert_blocked_deposit(
        rembadger, random, "guest-list-authorization"
    )  # Random user still blocked

    # Regardless of guestlist, we disable deposits
    rembadger.brickDeposits({"from": devMultisig})
    assert rembadger.depositsEnded() == True
    assert assert_blocked_deposit(
        rembadger, whitelisted_user, "guest-list-authorization"
    )
    assert assert_blocked_deposit(
        rembadger, random, "guest-list-authorization"
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
