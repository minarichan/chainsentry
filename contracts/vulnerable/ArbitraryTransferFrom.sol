pragma solidity ^0.8.0;

interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

/// Pulls tokens from an arbitrary `from` the caller chooses.
contract ArbitraryTransferFrom {
    IERC20 public token;

    constructor(IERC20 _token) {
        token = _token;
    }

    function deposit(address from, uint256 amount) public {
        require(token.transferFrom(from, address(this), amount), "pull failed");
    }
}
