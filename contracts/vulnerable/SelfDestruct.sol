pragma solidity ^0.8.0;

/// Anyone can destroy the contract.
contract SelfDestruct {
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    function destroy() public {
        selfdestruct(payable(msg.sender));
    }

    receive() external payable {}
}
