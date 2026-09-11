pragma solidity ^0.8.0;

/// Ether is withdrawn by the owner; the contract is never destroyed.
contract SafeSelfDestruct {
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    function withdraw() public {
        require(msg.sender == owner, "not owner");
        payable(owner).transfer(address(this).balance);
    }

    receive() external payable {}
}
