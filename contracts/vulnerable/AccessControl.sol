pragma solidity ^0.8.0;

/// Privileged withdrawal with no owner/role check.
contract AccessControl {
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    function withdraw() public {
        payable(msg.sender).transfer(address(this).balance);
    }

    receive() external payable {}
}
