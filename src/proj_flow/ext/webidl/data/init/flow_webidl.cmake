macro(__webidl_exec CONFIG EXT COMMAND)
    cmake_path(ABSOLUTE_PATH CONFIG OUTPUT_VARIABLE __ABS_CONFIG)
    cmake_path(RELATIVE_PATH __ABS_CONFIG OUTPUT_VARIABLE __CONFIG)

    execute_process(
        ECHO_OUTPUT_VARIABLE
        ECHO_ERROR_VARIABLE
        COMMAND_ERROR_IS_FATAL LAST
        COMMAND "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/.flow/flow.py" webidl ${COMMAND}
        --cfg "${__ABS_CONFIG}"
        --binary-dir "${PROJECT_BINARY_DIR}"
        ${ARGN}
    )
endmacro()

function(add_webidl_generation TARGET CONFIG)
    __webidl_exec("${CONFIG}" cmake cmake --target "${TARGET}")
    __webidl_exec("${CONFIG}" deps depfile)

    cmake_path(ABSOLUTE_PATH CONFIG)
    cmake_path(RELATIVE_PATH CONFIG)

    if(EXISTS "${CMAKE_CURRENT_BINARY_DIR}/${CONFIG}.cmake")
        include("${CMAKE_CURRENT_BINARY_DIR}/${CONFIG}.cmake")
    endif()
endfunction()
