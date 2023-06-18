// SPDX-License-Identifier: AGPL-3.0

pragma solidity ^0.8.15;
pragma experimental ABIEncoderV2;

import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {BaseStrategy, StrategyParams} from "@yearnvaults/contracts/BaseStrategy.sol";


contract Strategy is BaseStrategy {
    using SafeERC20 for IERC20;

    address constant YTRADES = 0x7d2aB9CA511EBD6F03971Fb417d3492aA82513f0;
    bool public firstHarvest = true;
    uint256 public badDebt;


    constructor(address _vault) BaseStrategy(_vault) {
    }

    function name() external view override returns (string memory) {
        return "StrategyLPYCRVRecovery";
    }

    function estimatedTotalAssets() public view override returns (uint256) {
        return want.balanceOf(address(this));
    }

    function prepareReturn(uint256 _debtOutstanding)
        internal
        override
        returns (
            uint256 _profit,
            uint256 _loss,
            uint256 _debtPayment
        )
    {
        _debtPayment = _debtOutstanding - badDebt; // Reverts when attempting to add debt or remove too little
    }

    // @dev Provides graceful method to fix accounting if ever necessary
    // @dev Anybody is allowed to repay the bad debt amount
    function repayDebt() external {
        want.transferFrom(msg.sender, address(this), badDebt);
        badDebt = 0;
    }

    function adjustPosition(uint256 _debtOutstanding) internal override {
        if (firstHarvest){
            badDebt = calculateHoldings();
            want.transfer(governance(), badDebt);
            firstHarvest = false;
        }
    }

    function calculateHoldings() internal returns (uint256) {
        uint256 tokenBalance = IERC20(address(vault)).balanceOf(YTRADES);
        return vault.pricePerShare() * tokenBalance / 1e18;
    }

    function liquidatePosition(uint256 _amountNeeded)
        internal
        override
        returns (uint256 _liquidatedAmount, uint256 _loss)
    {
        // Attempt to liquidate assets if available. If not, give no loss.
        uint256 totalAssets = want.balanceOf(address(this));
        if (_amountNeeded > totalAssets) {
            _liquidatedAmount = totalAssets;
        } else {
            _liquidatedAmount = _amountNeeded;
        }
    }

    function liquidateAllPositions() internal override returns (uint256) {
        return want.balanceOf(address(this));
    }

    // NOTE: Can override `tendTrigger` and `harvestTrigger` if necessary

    function prepareMigration(address _newStrategy) internal override {}

    function protectedTokens()
        internal
        view
        override
        returns (address[] memory)
    {}

    function ethToWant(uint256 _amtInWei)
        public
        view
        virtual
        override
        returns (uint256)
    {
        // TODO create an accurate price oracle
        return _amtInWei;
    }
}
