# ANALYTICS_FORMULAS.md

## Purpose

This document contains the exact mathematical definitions and equations for all calculations performed by the **JewelMind-AI** analytics engine.

To prevent hallucinations, the in-app AI Copilot relies on these formulas. Every numeric output returned by the backend must map to one of the equations defined below.

> [!IMPORTANT]
> **Multi-Tenancy Scoping Rule**: Every formula and function defined in this document operates implicitly on a single business's data. All input sets ($T$, $I$, $I_{\text{metal}}$, etc.) represent rows filtered to the `business_id` of the currently selected business. A calculation that crosses business boundaries is a critical data-isolation bug (see PROJECT_RULES.md, rule 11). This filtering is enforced in SQL/Pandas — it is **not** the LLM's responsibility.

---

## 1. Core Financial Metrics

Let $S$ be the `selling_price`, $D$ be the `discount`, $MC$ be the `making_charge`, and $C$ be the `cost_basis` for a single sale record in a given period $T$.

### A. Gross Revenue
The gross selling price before discounts and taxes.
$$\text{Gross Revenue}(T) = \sum_{i \in T} S_i$$

### B. Net Revenue
The actual revenue collected by the business.
$$\text{Net Revenue}(T) = \sum_{i \in T} (S_i - D_i)$$

### C. Cost of Goods Sold (COGS)
The cost basis of inventory items sold.
$$\text{COGS}(T) = \sum_{i \in T} C_i$$
*Note: For serialized items, $C_i$ is the exact `total_cost` from the purchase table of the matching tag.*

### D. Gross Profit (GP)
$$\text{Gross Profit}(T) = \text{Net Revenue}(T) - \text{COGS}(T) = \sum_{i \in T} (S_i - D_i - C_i)$$

### E. Gross Margin Percentage
$$\text{Gross Margin \%}(T) = \left( \frac{\text{Gross Profit}(T)}{\text{Net Revenue}(T)} \right) \times 100$$

---

## 2. Profit Diagnosis Engine (Variance Decomposition)

To explain *why* Gross Profit changed between a baseline period (Month $A$, e.g., May) and a target period (Month $B$, e.g., June), we decompose the total variance $\Delta GP = GP_B - GP_A$ into four independent, additive drivers.

Let:
*   $W_T = \sum_{i \in T} \text{weight}_i$ be the total weight sold (in grams).
*   $Q_{T, c}$ be the weight sold in category $c$ in period $T$.
*   $\text{Margin Rate}_{T} = \frac{GP_T}{W_T}$ be the average gross profit per gram in period $T$.
*   $\text{Margin Rate}_{T, c} = \frac{GP_{T,c}}{W_{T,c}}$ be the average gross profit per gram for category $c$.

### Equation 1: Sales Volume Effect ($\Delta GP_{\text{vol}}$)
The impact of selling more or less total weight, assuming base-period margins and category mix remained constant.
$$\Delta GP_{\text{vol}} = (W_B - W_A) \times \text{Margin Rate}_A$$

### Equation 2: Discount Variance Effect ($\Delta GP_{\text{disc}}$)
The impact of changes in the average discount rate per gram.
$$\Delta GP_{\text{disc}} = - \left( \frac{\sum_{i \in B} D_i}{W_B} - \frac{\sum_{j \in A} D_j}{W_A} \right) \times W_B$$

### Equation 3: Making-Charge Realization Effect ($\Delta GP_{\text{labor}}$)
The impact of changes in the average making charge labor rate billed per gram.
$$\Delta GP_{\text{labor}} = \left( \frac{\sum_{i \in B} MC_i}{W_B} - \frac{\sum_{j \in A} MC_j}{W_A} \right) \times W_B$$

### Equation 4: Product Mix Effect ($\Delta GP_{\text{mix}}$)
The impact of customers buying a higher/lower proportion of high-margin categories vs. low-margin categories.
$$\Delta GP_{\text{mix}} = \sum_{c} \left( \frac{W_{B,c}}{W_B} - \frac{W_{A,c}}{W_A} \right) \times W_B \times \text{Margin Rate}_{A,c}$$

### Equation 5: Metal Margin Effect ($\Delta GP_{\text{metal\_cost}}$)
The residual variance driven by fluctuations in raw metal acquisition cost vs. basic metal retail pricing.
$$\Delta GP_{\text{metal}} = \Delta GP - (\Delta GP_{\text{vol}} + \Delta GP_{\text{disc}} + \Delta GP_{\text{labor}} + \Delta GP_{\text{mix}})$$

---

## 3. Inventory Performance & Coverage

Let $I$ be the active inventory set (tagged items currently unsold in the vault).

### A. Inventory Ageing
For any item $j \in I$, let $t_{\text{current}}$ be today's date and $t_{\text{acq}, j}$ be its acquisition date (from purchases).
$$\text{Age}_j = t_{\text{current}} - t_{\text{acq}, j} \quad (\text{in days})$$

Ageing buckets are categorized by grouping inventory values:
*   **0-30 Days**: $\sum \text{total\_cost}_j \text{ for } \text{Age}_j \le 30$
*   **31-90 Days**: $\sum \text{total\_cost}_j \text{ for } 30 < \text{Age}_j \le 90$
*   **91-180 Days**: $\sum \text{total\_cost}_j \text{ for } 90 < \text{Age}_j \le 180$
*   **181-365 Days**: $\sum \text{total\_cost}_j \text{ for } 180 < \text{Age}_j \le 365$
*   **365+ Days (Dead Stock)**: $\sum \text{total\_cost}_j \text{ for } \text{Age}_j > 365$

### B. Stock Coverage (in Days)
Measures how long current inventory will last based on recent sales velocity.
$$\text{Stock Coverage}_c = \frac{\text{Current Stock Weight } (W_{\text{inv}, c})}{\text{Average Daily Sales Weight over past 30 days } (\bar{W}_{\text{sales}, c})}$$
where:
$$\bar{W}_{\text{sales}, c} = \frac{\text{Total Weight of category } c \text{ sold in past 30 days}}{30}$$

### C. Rule-Based Inventory Classification
*   **Fast Mover**: Top 20% of products in category $c$ by sales velocity, or items with $\text{Stock Coverage}_c < 15 \text{ days}$ (flagged as **Stockout Risk**).
*   **Slow Mover**: Items with $\text{Stock Coverage}_c > 180 \text{ days}$.
*   **Dead Stock Candidate**: Individual items with $\text{Age}_j > 180 \text{ days}$ AND 0 sales in its SKU/type over the past 90 days.

---

## 4. Valuation & Commodity Risk (Metal Exposure)

### A. Weighted Acquisition Rate (WAR)
The average metal cost basis per gram for active inventory of a specific metal (gold/silver).
$$\text{WAR}_{\text{metal}} = \frac{\sum_{k \in I_{\text{metal}}} \text{metal\_cost}_k}{\sum_{k \in I_{\text{metal}}} \text{net\_weight}_k}$$

### B. Valuation Exposure
Comparing the book value of inventory against today's reference board rate. Let $R_{\text{today, metal}}$ be the current rate per gram for the metal.
$$\text{Valuation Exposure}_{\text{metal}} = \sum_{k \in I_{\text{metal}}} \left( \text{net\_weight}_k \times (R_{\text{today, metal}} \times \text{Purity Ratio}_k - \text{WAR}_{\text{metal}}) \right)$$
where $\text{Purity Ratio}_k = \frac{\text{Purity of item } k \text{ in Karats}}{24}$ (or $1.0$ for Silver).

> [!NOTE]
> Valuation Exposure represents a *paper valuation fluctuation*, not a realized financial loss.

---

## 5. Scenario Simulator

Let $x$ be the percentage change in metal price input by the user (e.g., $x = -10$ for a 10% drop).

### A. Simulated Board Rate
$$R_{\text{sim, metal}} = R_{\text{today, metal}} \times \left(1 + \frac{x}{100}\right)$$

### B. Simulated Valuation Exposure
$$\text{Simulated Exposure}_{\text{metal}} = \sum_{k \in I_{\text{metal}}} \left( \text{net\_weight}_k \times (R_{\text{sim, metal}} \times \text{Purity Ratio}_k - \text{WAR}_{\text{metal}}) \right)$$

### C. Valuation Movement (Delta Impact)
The direct financial impact on paper holdings:
$$\Delta \text{Value}_{\text{metal}} = \text{Simulated Exposure}_{\text{metal}} - \text{Valuation Exposure}_{\text{metal}} = \sum_{k \in I_{\text{metal}}} \left( \text{net\_weight}_k \times R_{\text{today, metal}} \times \frac{x}{100} \times \text{Purity Ratio}_k \right)$$
This formula is computed per category to identify the most-exposed category segments.
