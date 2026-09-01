pragma solidity ^0.8.0;

interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

contract SafeTransferFrom {
    IERC20 public token;

    constructor(IERC20 _token) {
        token = _token;
    }

    function deposit(uint256 amount) public {
        require(token.transferFrom(msg.sender, address(this), amount), "pull failed");
    }

    function depositFor(address from, uint256 amount) public {
        require(from == msg.sender, "not owner");
        require(token.transferFrom(from, address(this), amount), "pull failed");
    }
}
