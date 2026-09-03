pragma solidity ^0.8.0;

interface INotifier {
    function notify(address account, uint256 amount) external;
}

/// Shared `reward` is still live when `harvest` calls out; `claim` can run first.
contract CrossFunctionReentrancy {
    INotifier public notifier;
    mapping(address => uint256) public reward;

    constructor(INotifier _notifier) {
        notifier = _notifier;
    }

    function harvest() public {
        uint256 pending = reward[msg.sender];
        require(pending > 0, "empty");
        notifier.notify(msg.sender, pending);
    }

    function claim() public {
        uint256 amount = reward[msg.sender];
        reward[msg.sender] = 0;
        payable(msg.sender).transfer(amount);
    }
}
