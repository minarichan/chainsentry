pragma solidity ^0.8.0;

interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

/// High-level token call before storage update (not address.transfer).
contract TokenReentrancy {
    IERC20 public token;
    mapping(address => uint256) public balances;

    constructor(IERC20 _token) {
        token = _token;
    }

    function withdraw() public {
        uint256 amount = balances[msg.sender];
        require(amount > 0, "empty");
        token.transferFrom(address(this), msg.sender, amount);
        balances[msg.sender] = 0;
    }
}
