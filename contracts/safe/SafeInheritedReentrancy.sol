pragma solidity ^0.8.0;

contract VaultStorage {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }
}

contract SafeInheritedReentrancy is VaultStorage {
    function withdraw() public {
        uint256 amount = balances[msg.sender];
        require(amount > 0, "empty");
        balances[msg.sender] = 0;
        (bool sent, ) = msg.sender.call{value: amount}("");
        require(sent, "failed");
    }
}
