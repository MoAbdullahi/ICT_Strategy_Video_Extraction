# Precise Mathematical Logic for ICT Trading Strategy Components

This document outlines the precise mathematical and algorithmic logic for the key Inner Circle Trader (ICT) concepts discussed in the video. These definitions are crucial for developing a robust and accurate Python implementation of the trading strategy.

## 1. Fair Value Gap (FVG)

A Fair Value Gap (FVG) is an inefficiency in price delivery, represented by a three-candle pattern. It signifies an area where price moved rapidly, leaving an imbalance. FVGs can be bullish (indicating potential support) or bearish (indicating potential resistance).

### 1.1. Bullish FVG (Buy Side Imbalance - BSI)

A **Bullish FVG** is identified by a three-candle sequence (Candle 1, Candle 2, Candle 3) where the low of Candle 1 is higher than the high of Candle 3. The FVG range is defined by the high of Candle 1 and the low of Candle 3.

*   **Condition:** `Low(Candle 1) > High(Candle 3)`
*   **Range:** `[High(Candle 1), Low(Candle 3)]`

### 1.2. Bearish FVG (Sell Side Imbalance - SSI)

A **Bearish FVG** is identified by a three-candle sequence (Candle 1, Candle 2, Candle 3) where the high of Candle 1 is lower than the low of Candle 3. The FVG range is defined by the low of Candle 1 and the high of Candle 3.

*   **Condition:** `High(Candle 1) < Low(Candle 3)`
*   **Range:** `[Low(Candle 1), High(Candle 3)]`

## 2. Balanced Price Range (BPR)

A **Balanced Price Range (BPR)** occurs when a bullish FVG and a bearish FVG overlap. This overlap signifies an area where price has aggressively moved in both directions, often creating a strong zone of support or resistance. The BPR is the intersection of the two FVG ranges.

*   **Condition:** An overlap exists between a Bullish FVG range `[BFVG_High1, BFVG_Low3]` and a Bearish FVG range `[SFVG_Low1, SFVG_High3]`.
*   **Range:** The intersection of the two FVG ranges. For example, if `BFVG_High1 < SFVG_High3` and `BFVG_Low3 > SFVG_Low1`, the BPR range would be `[max(BFVG_High1, SFVG_Low1), min(BFVG_Low3, SFVG_High3)]`.

## 3. Change in the State of Delivery (CISD) / Market Structure Shift (MSS)

A **Change in the State of Delivery (CISD)**, often referred to as a Market Structure Shift (MSS), indicates a significant alteration in market sentiment or trend. It is typically identified by the break of a significant swing high or swing low.

### 3.1. Swing High

A **Swing High** is a candle whose high is greater than the highs of at least `N` candles to its left and `N` candles to its right. A common value for `N` is 2.

*   **Condition:** `High(Current Candle) > High(Candle - i)` for `i` from 1 to `N`, and `High(Current Candle) > High(Candle + i)` for `i` from 1 to `N`.

### 3.2. Swing Low

A **Swing Low** is a candle whose low is lower than the lows of at least `N` candles to its left and `N` candles to its right. A common value for `N` is 2.

*   **Condition:** `Low(Current Candle) < Low(Candle - i)` for `i` from 1 to `N`, and `Low(Current Candle) < Low(Candle + i)` for `i` from 1 to `N`.

### 3.3. Bullish CISD (Break of Bearish Structure)

A **Bullish CISD** occurs when price breaks above a significant Swing High after a period of bearish price action. This signals a potential shift from a bearish to a bullish market structure.

*   **Condition:** Price closes above a confirmed Swing High.

### 3.4. Bearish CISD (Break of Bullish Structure)

A **Bearish CISD** occurs when price breaks below a significant Swing Low after a period of bullish price action. This signals a potential shift from a bullish to a bearish market structure.

*   **Condition:** Price closes below a confirmed Swing Low.

## 4. Multi-Timeframe (MTF) Alignment

**Multi-Timeframe (MTF) Alignment** involves establishing a trading bias on a higher timeframe and then seeking entry confirmations on lower timeframes. This creates a hierarchical decision-making process.

*   **Logic:**
    1.  **Higher Timeframe (e.g., Daily):** Identify the primary trend and key ICT levels (FVG, BPR) that are likely to act as major turning points or areas of interest. This establishes the overall market bias (e.g., "Daily Bearish Bias" if price is interacting with a Daily Bearish FVG).
    2.  **Lower Timeframe (e.g., 1-hour, 15-minute):** Once the higher timeframe bias is established and price interacts with a key higher timeframe level, look for confirmation signals on the lower timeframes. These confirmations typically include a CISD/MSS and an FVG inversion that aligns with the higher timeframe bias.
    3.  **Entry:** Execute trades on the lower timeframe only when the lower timeframe signals confirm the higher timeframe bias and interaction with a key level.

This structured approach ensures that trades are taken in alignment with the broader market context, increasing the probability of success and reducing noise from lower timeframe fluctuations.
