pragma solidity ^0.8.0;

/// Caller-supplied deadline — standard swap expiry, not a protocol time gate.
contract SwapDeadline {
    function swap(uint256, uint256 deadline) external {
        require(deadline >= block.timestamp, "expired");
    }
}
