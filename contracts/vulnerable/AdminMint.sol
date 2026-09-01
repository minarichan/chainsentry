pragma solidity ^0.8.0;

/// Unrestricted admin mint: amount is a parameter.
contract AdminMint {
    mapping(address => uint256) public balanceOf;

    function mint(address to, uint256 amount) external {
        balanceOf[to] += amount;
    }
}
