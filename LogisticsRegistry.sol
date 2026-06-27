// SPDX-License-Identifier: MIT
pragma solidity 0.8.26;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title LogisticsRegistry
 * @notice Records logistics checkpoints for DPP products on FME Layer1.
 *         Separate from TrueLayer1DPP so the product registry stays untouched.
 *         Each event: dppId -> status, location, sealIntact, note, timestamp.
 *
 *         For PoC: events are written by the owner (server-side key).
 *         Later: a JP Logistics API or a backend signer can call addEvent.
 */
contract LogisticsRegistry is Ownable {

    struct Event {
        string  status;      // e.g. "shipped", "hub_arrived", "delivered"
        string  location;    // e.g. "Tokyo Factory", "Osaka Hub"
        bool    sealIntact;  // tamper seal still good?
        string  note;        // optional free text
        uint256 timestamp;   // block time
    }

    // dppId => list of events (in order added)
    mapping(string => Event[]) private events;

    event LogisticsEventAdded(
        string indexed dppId,
        string status,
        string location,
        bool sealIntact,
        uint256 timestamp
    );

    constructor(address initialOwner) Ownable(initialOwner) {}

    /// Add one checkpoint for a product
    function addEvent(
        string memory dppId,
        string memory status,
        string memory location,
        bool sealIntact,
        string memory note
    ) public onlyOwner {
        events[dppId].push(Event(status, location, sealIntact, note, block.timestamp));
        emit LogisticsEventAdded(dppId, status, location, sealIntact, block.timestamp);
    }

    /// How many events a product has
    function eventCount(string memory dppId) external view returns (uint256) {
        return events[dppId].length;
    }

    /// Read one event by index
    function getEvent(string memory dppId, uint256 index)
        external view
        returns (string memory status, string memory location, bool sealIntact, string memory note, uint256 timestamp)
    {
        Event storage e = events[dppId][index];
        return (e.status, e.location, e.sealIntact, e.note, e.timestamp);
    }

    /// Read all events for a product at once
    function getAllEvents(string memory dppId) external view returns (Event[] memory) {
        return events[dppId];
    }
}
