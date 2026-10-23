# Register qualification even without the user's local game artifacts. Check at
# execution time so removing/restoring evidence cannot silently change coverage.
# This helper is also imported by the synthetic registration-contract project.
# Register the GPU/SDK-free RR comparison contract only in the real project.
if(PROJECT_NAME STREQUAL "RadeonRTRemaster")
    add_test(NAME rr_repeatability_contract COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tests/verify_rr_repeatability_contract.py)
    set_tests_properties(rr_repeatability_contract PROPERTIES TIMEOUT 10)
endif()

function(rrt_add_evidence_test name evidence_variable)
    add_test(NAME ${name} COMMAND "${Python3_EXECUTABLE}"
        "${PROJECT_SOURCE_DIR}/tests/run_evidence_test.py"
        --test-name "${name}" --evidence-variable "${evidence_variable}"
        --evidence "${${evidence_variable}}" -- ${ARGN})
    set_tests_properties(${name} PROPERTIES SKIP_RETURN_CODE 77 LABELS local_evidence)
endfunction()
