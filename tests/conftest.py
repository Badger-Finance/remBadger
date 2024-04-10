from brownie import (
    accounts,
    interface,
    Controller,
    RemBadger,
    BrikedStrategy
)
from config import (
    BADGER_DEV_MULTISIG,
    WANT,
    LP_COMPONENT,
    REWARD_TOKEN,
    PROTECTED_TOKENS,
    FEES,
)
from dotmap import DotMap
import pytest


@pytest.fixture
def deployed():
    """
    Deploys, vault, controller and strats and wires them up for you to test
    """
    a0 = accounts[0]

    strategist = a0
    keeper = a0
    guardian = a0

    governance = accounts.at(BADGER_DEV_MULTISIG, force=True)
    deployer = governance

    controller = Controller.deploy({"from": deployer})
    controller.initialize(BADGER_DEV_MULTISIG, strategist, keeper, BADGER_DEV_MULTISIG)

    sett = RemBadger.deploy({"from": deployer})
    sett.initialize(
        WANT,
        controller,
        BADGER_DEV_MULTISIG,
        keeper,
        guardian,
        False,
        "prefix",
        "PREFIX",
    )

    sett.unpause({"from": governance})
    controller.setVault(WANT, sett)

    ## TODO: Add guest list once we find compatible, tested, contract
    # guestList = VipCappedGuestListWrapperUpgradeable.deploy({"from": deployer})
    # guestList.initialize(sett, {"from": deployer})
    # guestList.setGuests([deployer], [True])
    # guestList.setUserDepositCap(100000000)
    # sett.setGuestList(guestList, {"from": governance})

    ## Start up Strategy
    strategy = BrikedStrategy.deploy({"from": deployer})
    strategy.initialize(
        BADGER_DEV_MULTISIG,
        strategist,
        controller,
        keeper,
        guardian,
        PROTECTED_TOKENS,
        FEES,
    )

    ## Tool that verifies bytecode (run independently) <- Webapp for anyone to verify

    ## Set up tokens
    want = interface.IERC20(WANT)
    lpComponent = interface.IERC20(LP_COMPONENT)
    rewardToken = interface.IERC20(REWARD_TOKEN)
    
    whale = accounts.at("0x4441776e6a5d61fa024a5117bfc26b953ad1f425", force=True)
    want.transfer(deployer, want.balanceOf(whale), {"from": whale})


    ## Wire up Controller to Strart
    ## In testing will pass, but on live it will fail
    controller.approveStrategy(WANT, strategy, {"from": governance})
    controller.setStrategy(WANT, strategy, {"from": deployer})

    return DotMap(
        deployer=deployer,
        controller=controller,
        vault=sett,
        sett=sett,
        strategy=strategy,
        governance=governance,
        # guestList=guestList,
        want=want,
        lpComponent=lpComponent,
        rewardToken=rewardToken,
    )


## Contracts ##

@pytest.fixture
def vault(deployed):
    return deployed.vault


@pytest.fixture
def sett(deployed):
    return deployed.sett


@pytest.fixture
def controller(deployed):
    return deployed.controller


@pytest.fixture
def strategy(deployed):
    return deployed.strategy


## Tokens ##


@pytest.fixture
def want(deployed):
    return deployed.want


@pytest.fixture
def tokens():
    return [WANT, LP_COMPONENT, REWARD_TOKEN]


## Accounts ##
@pytest.fixture
def governance(deployed):
    return deployed.governance

@pytest.fixture
def rando():
    return accounts[6]

@pytest.fixture
def deployer(deployed):
    return deployed.deployer


@pytest.fixture
def strategist(strategy):
    return accounts.at(strategy.strategist(), force=True)


@pytest.fixture
def settKeeper(vault):
    return accounts.at(vault.keeper(), force=True)


@pytest.fixture
def strategyKeeper(strategy):
    return accounts.at(strategy.keeper(), force=True)

@pytest.fixture
def rembadger():
    return RemBadger.at("0x6aF7377b5009d7d154F36FE9e235aE1DA27Aea22")

@pytest.fixture
def badger(rembadger):
    return interface.IERC20(rembadger.token())

@pytest.fixture
def devMultisig():
    return accounts.at("0xB65cef03b9B89f99517643226d76e286ee999e77", force=True)

@pytest.fixture
def proxy_admin():
    """
     Verify by doing web3.eth.getStorageAt("STRAT_ADDRESS", int(
        0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103
    )).hex()
    """
    return interface.IProxyAdmin("0x20Dce41Acca85E8222D6861Aa6D23B6C941777bF")


@pytest.fixture
def proxy_admin_gov():
    """
        Also found at proxy_admin.owner()
    """
    return accounts.at("0x21cf9b77f88adf8f8c98d7e33fe601dc57bc0893", force=True)


@pytest.fixture
def whitelisted_user():
    return accounts.at("0x138Dd537D56F2F2761a6fC0A2A0AcE67D55480FE", force=True)

@pytest.fixture
def whale():
    return accounts.at("0xD0A7A8B98957b9CD3cFB9c0425AbE44551158e9e", force=True)

@pytest.fixture
def random(want, whale):
    assert want.balanceOf(whale.address) > 0
    want.transfer(accounts[9].address, want.balanceOf(whale.address), {"from": whale})
    assert want.balanceOf(accounts[9].address) > 0
    return accounts[9]

## Forces reset before each test
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass