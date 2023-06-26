import brownie
from brownie import Contract
import pytest


def test_operation(
    chain, accounts, token, vault, strategy_convert, new_pool, new_vault, other_strats, user, gov, ytrades, strategist, amount, RELATIVE_APPROX
):
    strategy = strategy_convert
    want = Contract(strategy.want())
    chain.sleep(1)

    old_pool_supply_before = want.totalSupply()
    new_pool_supply_before = new_pool.totalSupply()
    vault_assets_before = new_vault.totalAssets()
    assert strategy.migratedDebt() == 0
    assert strategy.firstHarvest()

    tx = strategy.harvest()

    assert strategy.migratedDebt() > 0
    assert strategy.firstHarvest() == False
    assert old_pool_supply_before > want.totalSupply()
    assert new_pool_supply_before < new_pool.totalSupply()
    assert vault_assets_before < new_vault.totalAssets()
    assert new_vault.balanceOf(strategy) > 0


    # Gov balance went up
    print(f'Debt to migrate: {strategy.migratedDebt()/1e18}')
    print(f'Vault tokens minted: {new_vault.balanceOf(strategy)/1e18}')

    # Now let's invoke a user withdrawal to ensure he doesn't suffer losses, and only burns
    # and amount of vault tokens commensurate with what he's able to get out.
    pps_before = vault.pricePerShare()
    tx = vault.withdraw({"from": ytrades})
    assert pps_before == vault.pricePerShare()
    assert vault.balanceOf(ytrades) > 0
    # print(f'Amount returned: {tx.return_value / 1e18:,.2f}')
    # print(f'Vault tokens remaining: {tx.return_value / 1e18:,.2f}')
    assert want.balanceOf(vault) == 0

    # Verify that bad debt is == total debt
    stats = vault.strategies(strategy).dict()
    assert stats['totalDebt'] == strategy.migratedDebt()

    # Now lets tets a harvest with 0 debt ratio
    vault.updateStrategyDebtRatio(strategy, 0, {'from':gov})
    tx = strategy.harvest()
    stats = vault.strategies(strategy).dict()
    assert stats['totalDebt'] == strategy.migratedDebt()

    for s in other_strats:
        vault.updateStrategyDebtRatio(s, 0, {'from':gov})
        Contract(s, owner=gov).harvest()

    vault.updateStrategyDebtRatio(strategy, 10_000)
    # with brownie.reverts():
    #     tx = strategy.harvest() # Reverts because migrated debt exceeds debtOutstanding
    stats = vault.strategies(strategy).dict()
    assert stats['totalDebt'] == strategy.migratedDebt()

    vault.updateStrategyDebtRatio(strategy, 0)
    tx = strategy.harvest() # Harvest should succeed because debtOutstanding == migrated debt
    assert strategy.migratedDebt() == vault.strategies(strategy)['totalDebt']
    
    for s in other_strats:
        vault.updateStrategyDebtRatio(s, 5_000, {'from':gov})
        tx = Contract(s, owner=gov).harvest()
        loss = tx.events['StrategyReported']['loss']
        assert loss == 0

    repayer = accounts.at('0x5980d25B4947594c26255C0BF301193ab64ba803', force=True)
    want.approve(strategy, 2**256-1, {'from':repayer})
    strategy.repayDebt({'from':repayer})
    chain.mine()
    chain.sleep(1)
    assert strategy.estimatedTotalAssets() == vault.strategies(strategy)['totalDebt']
    
    tx = strategy.harvest()
    stats = vault.strategies(strategy).dict()
    assert stats['totalDebt'] == 0
    assert strategy.migratedDebt() == 0
    assert strategy.estimatedTotalAssets() == 0
    assert want.balanceOf(vault) > 0

    
    