import brownie
from brownie import Contract
import pytest


def test_operation(
    chain, accounts, token, vault, strategy, user, gov, ytrades, strategist, amount, RELATIVE_APPROX
):
    # harvest
    want = Contract(strategy.want())
    chain.sleep(1)
    gov_before = want.balanceOf(gov)
    tx = strategy.harvest()
    gov_after = want.balanceOf(gov)
    gain = gov_after - gov_before
    assert gain > 0
    assert gain == strategy.badDebt()
    assert strategy.firstHarvest() == False

    # Gov balance went up
    print(f'Bad Debt{strategy.badDebt()/1e18}')

    # Now let's invoke a user withdrawal to ensure he doesn't suffer losses, and only burns
    # and amount of vault tokens commensurate with what he's able to get out.
    pps_before = vault.pricePerShare()
    tx = vault.withdraw({"from": ytrades})
    assert pps_before == vault.pricePerShare()
    assert vault.balanceOf(ytrades) > 0
    print(f'Amount returned: {tx.return_value / 1e18:,.2f}')
    print(f'Vault tokens remaining: {tx.return_value / 1e18:,.2f}')
    assert want.balanceOf(vault) == 0

    # Verify that bad debt is == total debt
    stats = vault.strategies(strategy).dict()
    assert stats['totalDebt'] == strategy.badDebt()

    # Now lets tets a harvest with 0 debt ratio
    vault.updateStrategyDebtRatio(strategy, 0, {'from':gov})
    tx = strategy.harvest()
    stats = vault.strategies(strategy).dict()
    assert stats['totalDebt'] == strategy.badDebt()

def test_emergency_exit(
    chain, accounts, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX
):
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # set emergency and exit
    strategy.setEmergencyExit()
    chain.sleep(1)
    strategy.harvest()
    assert strategy.estimatedTotalAssets() < amount


def test_profitable_harvest(
    chain, accounts, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # TODO: Add some code before harvest #2 to simulate earning yield

    # Harvest 2: Realize profit
    chain.sleep(1)
    strategy.harvest()
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)
    profit = token.balanceOf(vault.address)  # Profits go to vault
    # TODO: Uncomment the lines below
    # assert token.balanceOf(strategy) + profit > amount
    # assert vault.pricePerShare() > before_pps


def test_change_debt(
    chain, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    chain.sleep(1)
    strategy.harvest()
    half = int(amount / 2)

    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == half

    vault.updateStrategyDebtRatio(strategy.address, 10_000, {"from": gov})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # In order to pass this tests, you will need to implement prepareReturn.
    # TODO: uncomment the following lines.
    # vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    # chain.sleep(1)
    # strategy.harvest()
    # assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == half


def test_sweep(gov, vault, strategy, token, user, amount, weth, weth_amount):
    # Strategy want token doesn't work
    token.transfer(strategy, amount, {"from": user})
    assert token.address == strategy.want()
    assert token.balanceOf(strategy) > 0
    with brownie.reverts("!want"):
        strategy.sweep(token, {"from": gov})

    # Vault share token doesn't work
    with brownie.reverts("!shares"):
        strategy.sweep(vault.address, {"from": gov})

    # TODO: If you add protected tokens to the strategy.
    # Protected token doesn't work
    # with brownie.reverts("!protected"):
    #     strategy.sweep(strategy.protectedToken(), {"from": gov})

    before_balance = weth.balanceOf(gov)
    weth.transfer(strategy, weth_amount, {"from": user})
    assert weth.address != strategy.want()
    assert weth.balanceOf(user) == 0
    strategy.sweep(weth, {"from": gov})
    assert weth.balanceOf(gov) == weth_amount + before_balance


def test_triggers(
    chain, gov, vault, strategy, token, amount, user, weth, weth_amount, strategist
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    chain.sleep(1)
    strategy.harvest()

    strategy.harvestTrigger(0)
    strategy.tendTrigger(0)