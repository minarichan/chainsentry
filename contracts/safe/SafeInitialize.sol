pragma solidity ^0.8.0;

contract SafeInitialize {
    address public owner;
    bool private _initializing;

    modifier initializer() {
        require(!_initializing, "already initialized");
        _initializing = true;
        _;
    }

    function initialize(address newOwner) public initializer {
        owner = newOwner;
    }
}
