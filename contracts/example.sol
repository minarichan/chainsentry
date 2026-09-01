pragma solidity ^0.8.0;

/// Minimal demo contract used by the Stage 1 "read and print" path.
contract Example {
    address public owner;
    uint256 public totalDeposits;
    mapping(address => uint256) public balances;

    event Deposited(address indexed account, uint256 amount);

    modifier onlyOwner() {
        require(msg.sender == owner, "not owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function deposit() external payable {
        balances[msg.sender] += msg.value;
        totalDeposits += msg.value;
        emit Deposited(msg.sender, msg.value);
    }

    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "insufficient");
        balances[msg.sender] -= amount;
        (bool sent, ) = payable(msg.sender).call{value: amount}("");
        require(sent, "transfer failed");
    }

    function transfer(address to, uint256 amount) external {
        require(balances[msg.sender] >= amount, "insufficient");
        balances[msg.sender] -= amount;
        balances[to] += amount;
    }

    function setOwner(address next) external onlyOwner {
        owner = next;
    }
}
