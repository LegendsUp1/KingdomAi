// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * KAIG Token — Upgradeable ERC-20 with Rebrand Capability
 * =========================================================
 *
 * WHY THIS ARCHITECTURE EXISTS:
 * The creator cannot afford trademark protection. If the name "KAIG" is
 * ever stolen, challenged, or must change, this contract allows the token
 * to be REBRANDED (name + ticker changed) without:
 *   - Redeploying the contract
 *   - Losing ANY user balances
 *   - Changing the contract address
 *   - Requiring users to do ANYTHING
 *
 * HOW IT WORKS:
 * - Uses OpenZeppelin's UUPS (Universal Upgradeable Proxy Standard)
 * - Token name and symbol are stored in MUTABLE storage variables
 * - Only the owner can call rebrand(newName, newSymbol)
 * - All balances, allowances, and total supply are UNTOUCHED by rebrand
 * - A MigrationExecuted event is emitted for full on-chain audit trail
 * - Previous identities are stored on-chain for transparency
 *
 * REAL-WORLD PRECEDENTS:
 * - MATIC → POL (Polygon, 2024): 1:1 swap, all balances preserved
 * - FTM → S (Fantom → Sonic, 2025): 1:1 automatic conversion
 * - MKR → SKY (MakerDAO, 2025): 1:1 migration via upgrade
 *
 * DEPLOYMENT:
 * 1. Deploy proxy pointing to this implementation
 * 2. Call initialize("KAI Gold", "KAIG", initialSupply)
 * 3. If rebrand needed: call rebrand("New Name", "NTICKER")
 *    → All balances stay exactly the same
 *    → Contract address stays exactly the same
 *    → Users see new name/ticker automatically
 */

import "@openzeppelin/contracts-upgradeable/token/ERC20/ERC20Upgradeable.sol";
import "@openzeppelin/contracts-upgradeable/token/ERC20/extensions/ERC20BurnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";

contract KAIGTokenV1 is
    Initializable,
    ERC20Upgradeable,
    ERC20BurnableUpgradeable,
    OwnableUpgradeable,
    UUPSUpgradeable
{
    // ── Mutable Identity (the whole point) ──────────────────────
    string private _tokenName;
    string private _tokenSymbol;

    // ── Rebrand History (on-chain audit trail) ──────────────────
    struct RebrandRecord {
        string oldName;
        string oldSymbol;
        string newName;
        string newSymbol;
        uint256 timestamp;
        string reason;
    }

    RebrandRecord[] public rebrandHistory;
    uint256 public identityVersion;

    // ── Buyback & Treasury ──────────────────────────────────────
    address public treasuryWallet;
    uint256 public buybackRateBps; // basis points (5000 = 50%)
    uint256 public transactionBurnRateBps; // basis points (10 = 0.1%)

    // ── Events ──────────────────────────────────────────────────
    event TokenRebranded(
        string oldName,
        string oldSymbol,
        string newName,
        string newSymbol,
        uint256 identityVersion,
        string reason,
        uint256 timestamp
    );

    event TreasuryUpdated(address oldTreasury, address newTreasury);
    event BuybackRateUpdated(uint256 oldRate, uint256 newRate);

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    /**
     * @notice Initialize the token (called once via proxy)
     * @param name_ Initial token name (e.g., "KAI Gold")
     * @param symbol_ Initial token symbol (e.g., "KAIG")
     * @param initialSupply Total supply to mint to deployer
     * @param treasury_ Treasury wallet for buyback routing
     */
    function initialize(
        string memory name_,
        string memory symbol_,
        uint256 initialSupply,
        address treasury_
    ) public initializer {
        __ERC20_init(name_, symbol_);
        __ERC20Burnable_init();
        __Ownable_init(msg.sender);
        __UUPSUpgradeable_init();

        _tokenName = name_;
        _tokenSymbol = symbol_;
        identityVersion = 1;
        treasuryWallet = treasury_;
        buybackRateBps = 5000; // 50%
        transactionBurnRateBps = 10; // 0.1%

        _mint(msg.sender, initialSupply * 10 ** decimals());
    }

    // ── Override name() and symbol() to use mutable storage ─────

    function name() public view virtual override returns (string memory) {
        return _tokenName;
    }

    function symbol() public view virtual override returns (string memory) {
        return _tokenSymbol;
    }

    // ═══════════════════════════════════════════════════════════
    // REBRAND — THE CRITICAL FUNCTION
    // ═══════════════════════════════════════════════════════════

    /**
     * @notice Rebrand the token (change name and/or ticker)
     * @dev ONLY changes labels. ALL balances, allowances, total supply
     *      remain EXACTLY the same. Contract address does not change.
     *      Users do not need to take any action.
     *
     * @param newName New token name
     * @param newSymbol New token symbol/ticker
     * @param reason Human-readable reason for rebrand (stored on-chain)
     */
    function rebrand(
        string memory newName,
        string memory newSymbol,
        string memory reason
    ) external onlyOwner {
        require(bytes(newName).length > 0, "Name cannot be empty");
        require(bytes(newSymbol).length > 0, "Symbol cannot be empty");

        // Store the old identity in history
        rebrandHistory.push(
            RebrandRecord({
                oldName: _tokenName,
                oldSymbol: _tokenSymbol,
                newName: newName,
                newSymbol: newSymbol,
                timestamp: block.timestamp,
                reason: reason
            })
        );

        string memory oldName = _tokenName;
        string memory oldSymbol = _tokenSymbol;

        // Update mutable identity
        _tokenName = newName;
        _tokenSymbol = newSymbol;
        identityVersion++;

        emit TokenRebranded(
            oldName,
            oldSymbol,
            newName,
            newSymbol,
            identityVersion,
            reason,
            block.timestamp
        );
    }

    // ── Query Functions ─────────────────────────────────────────

    /**
     * @notice Get the number of rebrands that have occurred
     */
    function rebrandCount() external view returns (uint256) {
        return rebrandHistory.length;
    }

    /**
     * @notice Get a specific rebrand record
     */
    function getRebrand(uint256 index) external view returns (RebrandRecord memory) {
        require(index < rebrandHistory.length, "Index out of bounds");
        return rebrandHistory[index];
    }

    /**
     * @notice Get the original (first) name and symbol
     */
    function originalIdentity() external view returns (string memory, string memory) {
        if (rebrandHistory.length == 0) {
            return (_tokenName, _tokenSymbol);
        }
        return (rebrandHistory[0].oldName, rebrandHistory[0].oldSymbol);
    }

    // ── Treasury & Buyback Management ───────────────────────────

    function setTreasury(address newTreasury) external onlyOwner {
        require(newTreasury != address(0), "Treasury cannot be zero");
        address old = treasuryWallet;
        treasuryWallet = newTreasury;
        emit TreasuryUpdated(old, newTreasury);
    }

    function setBuybackRate(uint256 newRateBps) external onlyOwner {
        require(newRateBps <= 10000, "Rate cannot exceed 100%");
        uint256 old = buybackRateBps;
        buybackRateBps = newRateBps;
        emit BuybackRateUpdated(old, newRateBps);
    }

    // ── UUPS Required Override ──────────────────────────────────

    function _authorizeUpgrade(
        address newImplementation
    ) internal override onlyOwner {}
}
