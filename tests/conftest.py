import pytest, requests
from brownie import config
from brownie import Contract, ZERO_ADDRESS

# @pytest.fixture(scope="session", autouse=True)
# def tenderly_fork(web3, chain):
#     fork_base_url = "https://simulate.yearn.network/fork"
#     payload = {"network_id": str(chain.id)}
#     resp = requests.post(fork_base_url, headers={}, json=payload)
#     fork_id = resp.json()["simulation_fork"]["id"]
#     fork_rpc_url = f"https://rpc.tenderly.co/fork/{fork_id}"
#     print(fork_rpc_url)
#     tenderly_provider = web3.HTTPProvider(fork_rpc_url, {"timeout": 600})
#     web3.provider = tenderly_provider
#     print(f"https://dashboard.tenderly.co/yearn/yearn-web/fork/{fork_id}")

@pytest.fixture
def gov(accounts):
    yield accounts.at("0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52", force=True)


@pytest.fixture
def user(accounts):
    whale = accounts.at('0x5980d25B4947594c26255C0BF301193ab64ba803', force=True)
    yield accounts[0]


@pytest.fixture
def rewards(accounts):
    yield accounts[1]


@pytest.fixture
def guardian(accounts):
    yield accounts[2]


@pytest.fixture
def management(accounts):
    yield accounts[3]


@pytest.fixture
def strategist(accounts):
    yield accounts[4]


@pytest.fixture
def keeper(accounts):
    yield accounts[5]


@pytest.fixture
def token():
    token_address = "0x6b175474e89094c44da98b954eedeac495271d0f"  # this should be the address of the ERC-20 used by the strategy/vault (DAI)
    yield Contract(token_address)


@pytest.fixture
def amount(accounts, token, user):
    amount = 10_000 * 10 ** token.decimals()
    # In order to get some funds for the token you are about to use,
    # it impersonate an exchange address to use it's funds.
    reserve = accounts.at("0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643", force=True)
    token.transfer(user, amount, {"from": reserve})
    yield amount


@pytest.fixture
def weth():
    token_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    yield Contract(token_address)


@pytest.fixture
def weth_amount(user, weth):
    weth_amount = 10 ** weth.decimals()
    user.transfer(weth, weth_amount)
    yield weth_amount


@pytest.fixture
def vault(user, gov):
    vault = Contract('0xc97232527B62eFb0D8ed38CF3EA103A6CcA4037e',owner=gov)
    vault.setLockedProfitDegradation(1e18,{'from':gov}) # We do instant-unlock to properly check pps affects
    return vault

@pytest.fixture
def other_strats(vault):
    strats = []
    for i in range(0,20):
        s = vault.withdrawalQueue(i)
        if s == ZERO_ADDRESS:
            break
        strats.append(s)
    yield strats

@pytest.fixture
def ytrades(user):
    return Contract('0x7d2aB9CA511EBD6F03971Fb417d3492aA82513f0',owner=user)

@pytest.fixture
def strategy_recover(strategist, keeper, vault, StrategyRecover, ytrades, gov, other_strats):
    strategy = strategist.deploy(StrategyRecover, vault)
    strategy.setKeeper(keeper)
    for s in other_strats:
        s = Contract(s, owner=gov)
        s.setDoHealthCheck(False)
        vault.updateStrategyDebtRatio(s, 0, {'from':gov})
        tx = s.harvest({'from':gov})
        assert tx.events['StrategyReported']['loss'] == 0
        vault.removeStrategyFromQueue(s, {'from':gov})
    assert vault.withdrawalQueue(0) == ZERO_ADDRESS
    total = vault.totalAssets()
    ytrades_amount = vault.balanceOf(ytrades) * vault.pricePerShare() / 1e18
    ratio = ytrades_amount / total * 10_000
    ratio += 100 # Add some buffer
    for s in other_strats:
        vault.updateStrategyDebtRatio(s, 10_000 / 2 - (ratio/2), {'from':gov})
        Contract(s).harvest({'from':gov})
    vault.addStrategy(strategy, 10_000 - vault.debtRatio(), 0, 2**256 - 1, 1_000, {"from": gov})
    yield strategy

@pytest.fixture
def strategy_convert(strategist, keeper, vault, StrategyLPConvert, ytrades, gov, other_strats):
    strategy = strategist.deploy(StrategyLPConvert, vault)
    strategy.setKeeper(keeper)
    for s in other_strats:
        s = Contract(s, owner=gov)
        s.setDoHealthCheck(False)
        vault.updateStrategyDebtRatio(s, 0, {'from':gov})
        tx = s.harvest({'from':gov})
        assert tx.events['StrategyReported']['loss'] == 0
        vault.removeStrategyFromQueue(s, {'from':gov})
    assert vault.withdrawalQueue(0) == ZERO_ADDRESS
    total = vault.totalAssets()
    ytrades_amount = vault.balanceOf(ytrades) * vault.pricePerShare() / 1e18
    ratio = ytrades_amount / total * 10_000
    ratio += 100 # Add some buffer
    for s in other_strats:
        vault.updateStrategyDebtRatio(s, 10_000 / 2 - (ratio/2), {'from':gov})
        Contract(s).harvest({'from':gov})
    vault.addStrategy(strategy, 10_000 - vault.debtRatio(), 0, 2**256 - 1, 1_000, {"from": gov})
    strategy.setParams([1,1],1,{'from':gov})
    yield strategy

@pytest.fixture
def new_pool():
    yield Contract('0x99f5aCc8EC2Da2BC0771c32814EFF52b712de1E5')

@pytest.fixture
def new_vault():
    yield Contract('0x6E9455D109202b426169F0d8f01A3332DAE160f3')

@pytest.fixture
def strategy(strategy_convert):
    yield strategy_convert

@pytest.fixture(scope="session")
def RELATIVE_APPROX():
    yield 1e-5


# Function scoped isolation fixture to enable xdist.
# Snapshots the chain before each test and reverts after test completion.
@pytest.fixture(scope="function", autouse=True)
def shared_setup(fn_isolation):
    pass
