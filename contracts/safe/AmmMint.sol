pragma solidity ^0.8.0;

/// Uniswap-style: anyone may call mint(address). Liquidity amount is not a parameter.
contract AmmMint {
    mapping(address => uint256) public balanceOf;
    uint256 public totalSupply;

    function mint(address to) external returns (uint256 liquidity) {
        liquidity = 1;
        totalSupply += liquidity;
        balanceOf[to] += liquidity;
    }
}
