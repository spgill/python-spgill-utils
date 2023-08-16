import os
import rich
import sys

if (
    not os.environ.get("SPGILL_UTILS_MUX_SUPPRESS_WARNING", "").lower()
    == "true"
):
    rich.print(
        "[yellow][italic]Warning:[/italic] The `spgill.utils.mux.*` modules have been deprecated. Consider replacing these modules in your\n"
        "script with their newer counterparts; they provide much stronger type annotations and improved workflows.\n"
        "You can suppress this warning by setting environment variable `SPGILL_UTILS_MUX_SUPPRESS_WARNING=True`\n"
        "- `spgill.utils.mux.edit` is now `spgill.utils.media.edit`\n"
        "- `spgill.utils.mux.info` is now `spgill.utils.media.info`\n"
        "- `spgill.utils.mux.merge` is now `spgill.utils.media.mux`\n",
        file=sys.stderr,
    )
