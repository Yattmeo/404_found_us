import pandas as pd
import json
import os

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COST_STRUCTURE_DIR = os.path.join(SCRIPT_DIR, "cost_structure")
MASTERCARD_FEE_FILE = os.path.join(COST_STRUCTURE_DIR, "masterCard_Card.JSON")
VISA_FEE_FILE = os.path.join(COST_STRUCTURE_DIR, "visa_Card.JSON")
MASTERCARD_NETWORK_FILE = os.path.join(COST_STRUCTURE_DIR, "masterCard_Network.JSON")
VISA_NETWORK_FILE = os.path.join(COST_STRUCTURE_DIR, "visa_Network.JSON")

# --- HELPERS ---
def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return []

def normalize_card_type(card_type):
    """Normalizes card types for network fee lookups."""
    if card_type in ["Debit (Prepaid)", "Prepaid"]:
        return "Debit"
    if card_type == "Super Premium Credit":
        return "Credit"
    return card_type

def get_network_fee(network, card_type, amount, net_structure):
    """Calculates network fees based on brand-specific rules."""
    if network == "Mastercard":
        base_fee = next((f for f in net_structure if "Acquirer Brand Volume" in f["fee_name"]), None)
        large_tx_fee = next((f for f in net_structure if "Transactions => 1000 USD" in f["fee_name"]), None)
        inquiry_fee = next((f for f in net_structure if "Account Status Inquiry Service Fee" in f["fee_name"]), None)
        
        pct = base_fee["percent_rate"] if base_fee else 0
        fixed = inquiry_fee["fixed_rate"] if inquiry_fee else 0
        
        if amount >= 1000.0 and large_tx_fee:
            pct += large_tx_fee["percent_rate"]
            
        return {"pct": pct / 100.0, "fixed": fixed}
        
    elif network == "Visa":
        norm_type = normalize_card_type(card_type)
        assess_fee = next((f for f in net_structure if "Acquirer Service Fee" in f["fee_name"] and f.get("card_type") == norm_type), None)
        proc_fee = next((f for f in net_structure if "Acquirer Processing Fee" in f["fee_name"] and f.get("card_type") == norm_type), None)
        
        pct = assess_fee["percent_rate"] if assess_fee else 0
        fixed = proc_fee["fixed_rate"] if proc_fee else 0
        
        return {"pct": pct / 100.0, "fixed": fixed}
    
    return {"pct": 0.0, "fixed": 0.0}

def append_row(rows_list, cost_type_id, network, brand, program, min_amt, max_amt, mcc, card_pct, card_fixed, net_fee):
    """Appends a row with percentages as strings with % sign."""
    net_pct = net_fee["pct"]
    net_fixed = net_fee["fixed"]
    
    def to_pct_str(val):
        return f"{(val * 100):.4f}%"
# --- INITIATISATION OF COLUMNS ---
    rows_list.append({
        "cost_type_ID": cost_type_id,
        "card_network": network,
        "card_brand": brand,
        "fee_program": program,
        "min_transaction_amt": round(min_amt, 4) if min_amt not in [0, 5, 1000] else min_amt,
        "max_transaction_amt": round(max_amt, 4) if max_amt not in [5, 999.99, 99999999] else max_amt,
        "mcc": mcc if mcc else "N/A",
        "card_fee_percent": to_pct_str(card_pct),
        "card_fee_dollars": round(card_fixed, 4),
        "network_fee_percent": to_pct_str(net_pct),
        "network_fee_dollars": round(net_fixed, 4),
        "subtotal_fee_percent": to_pct_str(card_pct + net_pct),
        "subtotal_fee_dollars": round(card_fixed + net_fixed, 4)
    })
    return cost_type_id + 1

def generate_cost_permutations():
    # --- CALCULATION OF AVAILABLE PERMUTATIONS ---
    permutations = []
    cost_type_id = 1
    
    configs = [
        {"network": "Visa", "card": VISA_FEE_FILE, "net": VISA_NETWORK_FILE},
        {"network": "Mastercard", "card": MASTERCARD_FEE_FILE, "net": MASTERCARD_NETWORK_FILE}
    ]
    
    for config in configs:
        network = config["network"]
        card_rules = load_json(config["card"])
        net_rules = load_json(config["net"])
        
        for rule in card_rules:
            brand = rule.get("card_type", "Unknown")
            program = rule.get("product", "Unknown")
            mcc = rule.get("mcc", "N/A")
            
            card_pct = rule.get("percent_rate", 0) / 100.0
            card_fixed = rule.get("fixed_rate", 0)
            max_fee = rule.get("max_fee", None)
            min_fee = rule.get("min_fee", None)
            
            is_small_ticket = "Small Ticket" in program
            base_min = rule.get("min_amount", 0 if is_small_ticket else 5.0)
            base_max = rule.get("max_amount", 5.0 if is_small_ticket else 99999999.0)
            
            # --- IDENTIFICAITON OF BREAKPOINT (IF ANY) ---
            breakpoints = {base_min, base_max}
            
            calc_min_bp = None
            if min_fee is not None and card_pct > 0:
                calc_min_bp = (min_fee - card_fixed) / card_pct
                if base_min < calc_min_bp < base_max:
                    breakpoints.add(calc_min_bp)
                    
            calc_max_bp = None
            if max_fee is not None and card_pct > 0:
                calc_max_bp = (max_fee - card_fixed) / card_pct
                if base_min < calc_max_bp < base_max:
                    breakpoints.add(calc_max_bp)
                    
            if network == "Mastercard" and not is_small_ticket and base_max > 1000:
                if base_min < 1000.0 < base_max:
                    breakpoints.add(1000.0)
                    
            # Sort the breakpoints to form sequential valid tiers
            sorted_bps = sorted(list(breakpoints))
            
            # Generate a row for each segmented tier
            for i in range(len(sorted_bps) - 1):
                tier_min = sorted_bps[i]
                tier_max = sorted_bps[i+1]
                
                # Use the midpoint to cleanly determine which fee rules apply to this specific chunk
                midpoint = (tier_min + tier_max) / 2.0
                
                tier_pct = card_pct
                tier_fixed = card_fixed
                
                # Check if this segment's amounts fall strictly into the min/max fee override zones
                if calc_min_bp is not None and midpoint < calc_min_bp:
                    tier_pct = 0.0
                    tier_fixed = min_fee
                elif calc_max_bp is not None and midpoint > calc_max_bp:
                    tier_pct = 0.0
                    tier_fixed = max_fee
                    
                # Calculate network fee (Use an amount within the tier boundary)
                net_fee_amt = tier_min if tier_min > 0 else 1.0
                net_fee = get_network_fee(network, brand, net_fee_amt, net_rules)
                
                cost_type_id = append_row(permutations, cost_type_id, network, brand, program, 
                                          tier_min, tier_max, mcc, tier_pct, tier_fixed, net_fee)

    return pd.DataFrame(permutations)

def main():
    output_filename = "cost_type_id_generated.csv"
    output_path = os.path.abspath(os.path.join(SCRIPT_DIR, output_filename))
    
    try:
        df = generate_cost_permutations()
        if not df.empty:
            # df.to_csv overwrites existing files if exists
            df.to_csv(output_path, index=False)
            print(f"✅ Successfully generated and OVERWROTE: {output_path}")
            print(f"📊 Total Rows: {len(df)}")
        else:
            print("⚠️ No data generated from JSON files.")
    except Exception as e:
        print(f"❌ Critical Error: {str(e)}")

if __name__ == "__main__":
    main()