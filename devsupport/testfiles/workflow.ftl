# A small Afrikaans Fluent file for exercising Virtaal's Fluent
# support (open via the "Fluent file" filter) - Fluent is monolingual
# (one file per locale, no separate source/target), so
# translate.storage.fluent.FluentUnit reports the message's own value
# as both source and target. unread-messages exercises Fluent's
# selector syntax (its own plural-equivalent mechanism), which the
# generic curly-brace placeable parser protects as an opaque unit
# without understanding its structure.
#
# Requires the fluent.syntax package (translate-toolkit's own "fluent"
# extra, a declared dependency) to open.
open = Maak oop
save = Stoor
cancel = Kanselleer

unread-messages = { $count ->
    [one] Jy het { $count } ongelese boodskap
   *[other] Jy het { $count } ongelese boodskappe
}
