pragma solidity ^0.8.0;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
}

contract SafeErc20Return {
    IERC20 public token;

    constructor(IERC20 _token) {
        token = _token;
    }

    function payout(address to, uint256 amount) public {
        require(token.transfer(to, amount), "transfer failed");
    }
}
