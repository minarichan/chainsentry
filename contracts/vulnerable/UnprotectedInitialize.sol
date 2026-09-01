pragma solidity ^0.8.0;

/// Public initialize with no initializer guard — proxy takeover.
contract UnprotectedInitialize {
    address public owner;

    function initialize(address newOwner) public {
        owner = newOwner;
    }
}
