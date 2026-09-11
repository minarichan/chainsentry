pragma solidity ^0.8.0;

/// External interaction uses call, not delegatecall, to a stored target.
contract SafeDelegateCall {
    address public target;

    constructor(address _target) {
        target = _target;
    }

    function execute(bytes calldata data) external {
        (bool ok, ) = target.call(data);
        require(ok, "call failed");
    }
}
