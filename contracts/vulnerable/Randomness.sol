pragma solidity ^0.8.0;

/// Predictable "random" winner from block attributes.
contract Randomness {
    address[] public players;

    function enter() external payable {
        require(msg.value == 0.01 ether, "entry fee");
        players.push(msg.sender);
    }

    function pickWinner() external {
        require(players.length > 0, "no players");
        uint256 index = uint256(keccak256(abi.encodePacked(block.timestamp, block.difficulty, players.length))) % players.length;
        address winner = players[index];
        players = new address[](0);
        payable(winner).transfer(address(this).balance);
    }
}
