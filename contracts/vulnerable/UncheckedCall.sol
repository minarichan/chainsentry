pragma solidity ^0.8.0;

/// Low-level call whose success flag is discarded.
contract UncheckedCall {
    address public recipient;

    constructor(address _recipient) {
        recipient = _recipient;
    }

    function payout(uint256 amount) external {
        payable(recipient).call{value: amount}("");
    }

    receive() external payable {}
}
