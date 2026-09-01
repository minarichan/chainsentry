pragma solidity ^0.8.0;

/// Authorization uses tx.origin instead of msg.sender.
contract TxOrigin {
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    function withdraw() external {
        require(tx.origin == owner, "not owner");
        payable(owner).transfer(address(this).balance);
    }
}
