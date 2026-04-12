"""
orderbook.py — Maintains the live bid and ask sides of the order book.

Uses heap-based data structures for O(log n) insertion and O(1) best-price
access. Bids use a max-heap (negated prices in Python's min-heap).
Asks use a natural min-heap. Cancelled orders use lazy deletion.
"""
