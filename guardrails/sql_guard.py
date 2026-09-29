import sqlglot
from sqlglot import exp


FORBIDDEN_EXPRESSIONS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.Copy,
    exp.Attach,
    exp.Pragma,
)


def validate_sql(query):
    """Validate one read-only query and normalize its result limit."""
    if not isinstance(query, str) or not query.strip():
        return False, "Query must be a non-empty SQL string."

    try:
        statements = sqlglot.parse(query, read="duckdb")
    except sqlglot.ParseError as error:
        return False, f"Invalid SQL: {error}"

    if len(statements) != 1:
        return False, "Only one SQL statement is allowed."

    statement = statements[0]
    if not isinstance(statement, (exp.Select, exp.Union)):
        return False, "Only SELECT or WITH statements are allowed."
    if statement.find(*FORBIDDEN_EXPRESSIONS):
        return False, "The query contains a forbidden SQL operation."

    limit = statement.args.get("limit")
    if limit is None:
        statement = statement.limit(1000)
    else:
        limit_value = limit.expression
        if isinstance(limit_value, exp.Literal) and limit_value.is_number:
            if int(limit_value.this) > 1000:
                limit.set("expression", exp.Literal.number(1000))
        else:
            return False, "LIMIT must be a numeric value no greater than 1000."

    return True, statement.sql(dialect="duckdb")
