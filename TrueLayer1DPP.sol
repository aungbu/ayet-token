// SPDX-License-Identifier: MIT
pragma solidity 0.8.26;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title TrueLayer1DPP
 * @notice Digital Product Passport proof registry for FME Layer1.
 *         Combines 5 registries in one contract for a PoC:
 *         1. Product Registry   - DPP ID -> product/SKU/edition/batch
 *         2. License Proof       - DPP ID -> IP holder/licensee/territory/term
 *         3. Tag Registry        - DPP ID -> NFC tag ID / tamper status
 *         4. Certificate Proof   - DPP ID -> document hash
 *         5. Ownership Proof     - DPP ID -> email hash (no wallet needed)
 *
 *         On-chain we store ONLY: IDs, hashes, status flags, timestamps.
 *         No personal data, no contract text, no private business info.
 */
contract TrueLayer1DPP is Ownable {

    // ---- 1. PRODUCT REGISTRY ----
    struct Product {
        string  sku;          // e.g. "JIP-DLX"
        uint256 edition;      // e.g. 1847
        uint256 totalEditions;// e.g. 10000
        string  batch;        // production batch reference
        string  origin;       // e.g. "Tokyo, Japan"
        uint256 createdAt;    // block timestamp
        bool    exists;
    }

    // ---- 2. LICENSE PROOF ----
    struct License {
        string  ipHolder;     // e.g. "Publisher Alpha"
        string  licensee;     // e.g. "Licensed Maker A"
        string  territory;    // e.g. "Japan / Global"
        string  licenseNo;    // e.g. "LIC-2026-0042"
        uint256 registeredAt;
        bool    exists;
    }

    // ---- 3. TAG REGISTRY ----
    struct Tag {
        string  nfcId;        // NFC tag UID (or hash of it)
        bool    sealIntact;   // tamper status
        uint256 linkedAt;
        bool    exists;
    }

    // ---- 4. CERTIFICATE PROOF ----
    struct Certificate {
        bytes32 docHash;      // keccak256 of the certificate/inspection doc
        uint256 anchoredAt;
        bool    exists;
    }

    // ---- 5. OWNERSHIP PROOF ----
    struct Ownership {
        bytes32 emailHash;    // keccak256 of owner email - never the email itself
        uint256 claimedAt;
        bool    claimed;
    }

    // dppId (string, e.g. "JIP-DLX-001847") => record
    mapping(string => Product)     public products;
    mapping(string => License)     public licenses;
    mapping(string => Tag)         public tags;
    mapping(string => Certificate) public certificates;
    mapping(string => Ownership)   public ownerships;

    // list of all DPP IDs for enumeration
    string[] public dppIds;
    mapping(string => bool) private dppIdSeen;

    // ---- EVENTS (these show up in the explorer as logs) ----
    event ProductRegistered(string indexed dppId, string sku, uint256 edition, uint256 timestamp);
    event LicenseRegistered(string indexed dppId, string ipHolder, string licensee, uint256 timestamp);
    event TagLinked(string indexed dppId, string nfcId, bool sealIntact, uint256 timestamp);
    event CertificateAnchored(string indexed dppId, bytes32 docHash, uint256 timestamp);
    event OwnershipClaimed(string indexed dppId, bytes32 emailHash, uint256 timestamp);

    constructor(address initialOwner) Ownable(initialOwner) {}

    function _track(string memory dppId) internal {
        if (!dppIdSeen[dppId]) {
            dppIdSeen[dppId] = true;
            dppIds.push(dppId);
        }
    }

    // ---- 1. register a product ----
    function registerProduct(
        string memory dppId,
        string memory sku,
        uint256 edition,
        uint256 totalEditions,
        string memory batch,
        string memory origin
    ) external onlyOwner {
        products[dppId] = Product(sku, edition, totalEditions, batch, origin, block.timestamp, true);
        _track(dppId);
        emit ProductRegistered(dppId, sku, edition, block.timestamp);
    }

    // ---- 2. register a license ----
    function registerLicense(
        string memory dppId,
        string memory ipHolder,
        string memory licensee,
        string memory territory,
        string memory licenseNo
    ) external onlyOwner {
        licenses[dppId] = License(ipHolder, licensee, territory, licenseNo, block.timestamp, true);
        _track(dppId);
        emit LicenseRegistered(dppId, ipHolder, licensee, block.timestamp);
    }

    // ---- 3. link a physical tag ----
    function linkTag(
        string memory dppId,
        string memory nfcId,
        bool sealIntact
    ) external onlyOwner {
        tags[dppId] = Tag(nfcId, sealIntact, block.timestamp, true);
        _track(dppId);
        emit TagLinked(dppId, nfcId, sealIntact, block.timestamp);
    }

    // ---- 4. anchor a certificate hash ----
    function anchorCertificate(
        string memory dppId,
        bytes32 docHash
    ) external onlyOwner {
        certificates[dppId] = Certificate(docHash, block.timestamp, true);
        _track(dppId);
        emit CertificateAnchored(dppId, docHash, block.timestamp);
    }

    // ---- 5. claim ownership (owner registers on behalf of collector) ----
    function claimOwnership(
        string memory dppId,
        bytes32 emailHash
    ) external onlyOwner {
        ownerships[dppId] = Ownership(emailHash, block.timestamp, true);
        _track(dppId);
        emit OwnershipClaimed(dppId, emailHash, block.timestamp);
    }

    // ---- convenience: register product + license + tag in one transaction ----
    function registerFull(
        string memory dppId,
        string memory sku,
        uint256 edition,
        uint256 totalEditions,
        string memory batch,
        string memory origin,
        string memory ipHolder,
        string memory licensee,
        string memory territory,
        string memory licenseNo,
        string memory nfcId
    ) external onlyOwner {
        products[dppId] = Product(sku, edition, totalEditions, batch, origin, block.timestamp, true);
        licenses[dppId] = License(ipHolder, licensee, territory, licenseNo, block.timestamp, true);
        tags[dppId]     = Tag(nfcId, true, block.timestamp, true);
        _track(dppId);
        emit ProductRegistered(dppId, sku, edition, block.timestamp);
        emit LicenseRegistered(dppId, ipHolder, licensee, block.timestamp);
        emit TagLinked(dppId, nfcId, true, block.timestamp);
    }

    // ---- read helpers ----
    function totalDPPs() external view returns (uint256) {
        return dppIds.length;
    }

    function isAuthentic(string memory dppId) external view returns (bool) {
        return products[dppId].exists && licenses[dppId].exists;
    }
}
