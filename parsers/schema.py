# Every parser returns a DataFrame with exactly these columns,
# so the rest of Finsight never needs to know which bank a file came from.
#
# "details" holds extra free text (payment reference, ING "Mededelingen")
# that the categorizer searches alongside "description".
#
# "account" identifies the user's own account the transaction belongs to
# (an IBAN, or e.g. "Revolut Current EUR"). "counterparty_account" is the
# other side's account number when the bank provides it. Both are used to
# recognize transfers between the user's own accounts.
#
# "fee" is a charge NOT already included in "amount". It is counted as an
# expense on top of the amount.

STANDARD_COLUMNS = [
    "date",
    "description",
    "details",
    "account",
    "counterparty_account",
    "amount",
    "currency",
    "bank",
    "transaction_type",
    "fee",
    "balance",
    "category",
]
