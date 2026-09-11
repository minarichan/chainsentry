pragma solidity ^0.8.0;

/// Winner is chosen from a caller-supplied index, not block attributes. Payout is owner-gated.
contract SafeRandomness {
    address public owner;
    address[] public players;

    constructor() {
        owner = msg.sender;
    }

    function enter() external payable {
        require(msg.value == 0.01 ether, "entry fee");
        players.push(msg.sender);
    }

    function pickWinner(uint256 index) external {
        require(msg.sender == owner, "not owner");
        require(players.length > 0, "no players");
        require(index < players.length, "bad index");
        address winner = players[index];
        players = new address[](0);
        payable(winner).transfer(address(this).balance);
    }
}
