pragma solidity ^0.8.0;

/// Vulnerable body is declared on the base; the child does not override it.
contract BaseReentrancy {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw() public {
        uint256 amount = balances[msg.sender];
        require(amount > 0, "empty");
        (bool sent, ) = msg.sender.call{value: amount}("");
        require(sent, "failed");
        balances[msg.sender] = 0;
    }
}

contract ChildReentrancy is BaseReentrancy {}
