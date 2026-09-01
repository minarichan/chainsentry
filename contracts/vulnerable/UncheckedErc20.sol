pragma solidity ^0.8.0;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
}

/// Ignores the ERC-20 success flag.
contract UncheckedErc20 {
    IERC20 public token;

    constructor(IERC20 _token) {
        token = _token;
    }

    function payout(address to, uint256 amount) public {
        token.transfer(to, amount);
    }
}
