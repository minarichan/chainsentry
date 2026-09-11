pragma solidity ^0.8.0;

/// Low-level call success is required before continuing.
contract SafeUncheckedCall {
    address public recipient;

    constructor(address _recipient) {
        recipient = _recipient;
    }

    function payout(uint256 amount) external {
        (bool ok, ) = payable(recipient).call{value: amount}("");
        require(ok, "call failed");
    }

    receive() external payable {}
}
