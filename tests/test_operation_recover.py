import brownie
from brownie import Contract
import pytest


def test_operation(
    chain, accounts, token, vault, strategy, other_strats, user, gov, ytrades, strategist, amount, RELATIVE_APPROX
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

    for s in other_strats:
        vault.updateStrategyDebtRatio(s, 0, {'from':gov})
        Contract(s, owner=gov).harvest()

    vault.updateStrategyDebtRatio(strategy, 10_000)
    with brownie.reverts():
        tx = strategy.harvest() # Reverts because badDebt exceeds debtOutstanding
    stats = vault.strategies(strategy).dict()
    assert stats['totalDebt'] == strategy.badDebt()

    vault.updateStrategyDebtRatio(strategy, 0)
    tx = strategy.harvest() # Harvest should succeed because debtOutstanding == badDebt
    assert strategy.badDebt() == vault.strategies(strategy)['totalDebt']
    
    want.approve(strategy, 2**256-1, {'from':gov})
    strategy.repayDebt({'from':gov})
    tx = strategy.harvest()
    stats = vault.strategies(strategy).dict()
    assert stats['totalDebt'] == 0
    assert strategy.badDebt() == 0
    assert strategy.estimatedTotalAssets() == 0
    assert want.balanceOf(vault) > 0
