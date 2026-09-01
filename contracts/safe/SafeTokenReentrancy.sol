pragma solidity ^0.8.0;

interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

/// Storage is updated before the ERC20 call.
contract SafeTokenReentrancy {
    IERC20 public token;
    mapping(address => uint256) public balances;

    constructor(IERC20 _token) {
        token = _token;
    }

    function withdraw() public {
        uint256 amount = balances[msg.sender];
        require(amount > 0, "empty");
        balances[msg.sender] = 0;
        require(token.transferFrom(address(this), msg.sender, amount));
    }
}
