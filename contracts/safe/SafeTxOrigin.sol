pragma solidity ^0.8.0;

/// Authorization uses msg.sender, not tx.origin.
contract SafeTxOrigin {
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    function withdraw() external {
        require(msg.sender == owner, "not owner");
        payable(owner).transfer(address(this).balance);
    }

    receive() external payable {}
}
