# Register qualification even without the user's local game artifacts. Check at
# execution time so removing/restoring evidence cannot silently change coverage.
function(rrt_add_evidence_test name evidence_variable)
    add_test(NAME ${name} COMMAND "${Python3_EXECUTABLE}"
        "${PROJECT_SOURCE_DIR}/tests/run_evidence_test.py"
        --test-name "${name}" --evidence-variable "${evidence_variable}"
        --evidence "${${evidence_variable}}" -- ${ARGN})
    set_tests_properties(${name} PROPERTIES SKIP_RETURN_CODE 77 LABELS local_evidence)
endfunction()
