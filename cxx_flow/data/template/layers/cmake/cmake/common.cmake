function(add_project_test TARGET)
  cmake_parse_arguments(PARSE_ARGV 1 TST "" "" "")
  add_executable(${TARGET}-test ${TST_UNPARSED_ARGUMENTS})
  set_target_properties(${TARGET}-test PROPERTIES FOLDER tests)
  target_compile_options(${TARGET}-test PRIVATE {{${}}{{NAME_PREFIX}}_ADDITIONAL_COMPILE_FLAGS})
  target_link_options(${TARGET}-test PRIVATE {{${}}{{NAME_PREFIX}}_ADDITIONAL_LINK_FLAGS})
  target_include_directories(${TARGET}-test
    PRIVATE
      ${CMAKE_CURRENT_SOURCE_DIR}/tests
      ${CMAKE_CURRENT_BINARY_DIR})
  fix_vs_modules(${TARGET}-test)
  set(VS_MODS ${VS_MODS} PARENT_SCOPE)
endfunction()
