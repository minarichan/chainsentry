pragma solidity ^0.8.0;

/// Auction end time depends on block.timestamp.
contract Timestamp {
    uint256 public auctionEnd;
    address public highestBidder;
    uint256 public highestBid;

    constructor(uint256 duration) {
        auctionEnd = block.timestamp + duration;
    }

    function bid() external payable {
        require(block.timestamp < auctionEnd, "ended");
        require(msg.value > highestBid, "too low");
        highestBidder = msg.sender;
        highestBid = msg.value;
    }

    function winner() external view returns (address) {
        require(block.timestamp >= auctionEnd, "active");
        return highestBidder;
    }
}
