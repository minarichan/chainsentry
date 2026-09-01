pragma solidity ^0.8.0;

/// delegatecall to a caller-supplied target.
contract DelegateCall {
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    function execute(address target, bytes calldata data) external {
        (bool ok, ) = target.delegatecall(data);
        require(ok, "delegatecall failed");
    }
}
