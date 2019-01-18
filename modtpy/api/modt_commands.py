import json


command_indexes = {
        'bio_get_version': 0, 'bio_get_serial': 1,

        'gpio_get_raw': 2, 'gpio_input_get': 3, 'gpio_output_set': 4,
        'gcode_process_command': 5, 'gcode_process_macro': 6,

        'heater_param_set': 7, 'heater_param_get': 8, 'heater_param_set_defaults': 9,
        'heater_var_set_defaults': 10, 'heater_turn_on': 11, 'heater_turn_off': 12,
        'heater_in_guardband': 13, 'heater_state_get': 14, 'heater_fault_get': 15,
        'heater_var_set': 16, 'heater_var_get': 17,

        'wifi_start_wifi': 18, 'wifi_stop_wifi': 19, 'wifi_client_connect': 20,
        'wifi_disconnect': 21,
        'wifi_client_get_status': 22, 'wifi_client_get_configuration': 23,
        'wifi_save_configuration': 24,
        'wifi_set_auto_start_configuration_item': 25,
        'wifi_set_auto_connect_configuration_item': 26,
        'wifi_set_auto_connect_ssid_configuration_item': 27,
        'wifi_set_auto_connect_key_configuration_item': 28, 'wifi_client_configure': 29,

        'servo_dc_config_get': 30, 'servo_dc_config_set': 31, 'servo_dc_move_default': 32,
        'servo_dc_move': 33, 'servo_dc_move_start_sync': 34, 'servo_dc_move_active': 35,
        'servo_dc_put_idle': 36, 'servo_dc_move_modify': 37, 'servo_dc_move_modifier_validate': 38,
        'servo_dc_move_metrics_get': 39, 'servo_dc_move_dir_get': 40, 'servo_dc_position_get': 41,
        'servo_dc_position_get_client': 42, 'servo_dc_position_set': 43,
        'servo_dc_position_set_client': 44,
        'servo_dc_target_get_client': 45, 'servo_dc_units_client_to_native': 46,
        'servo_dc_units_native_to_client': 47, 'servo_dc_name_str_get': 48,
        'servo_dc_backlash_set': 49,
        'servo_dc_trace_enable': 50,

        'unload_initiate': 51, 'load_initiate': 52,
        'Enter_dfu_mode': 53,
        'ui_led': 54,

        'sd_mmc_write': 55, 'sd_mmc_write_byte': 56, 'sd_mmc_read_byte': 57, 'sd_mmc_read': 58,
        'sd_mmc_get_storage_info': 59,

        'hbridge_duty_set': 60,

        'wifi_client_scan_refresh': 61, 'wifi_client_scan_get': 62,

        'jm_disable_network_tasks': 63, 'jm_enable_network_tasks': 64,
        'jm_are_network_tasks_enabled': 65, 'check_store_connection': 66,

        'Reset_printer': 67,
        'transport': 68}


def get_checksum(command_payload):
    size = len(command_payload.replace(" ", ""))
    return ("%0.2X%0.2X%0.2X%0.2X%0.2X" % (36, size, 0, 255 - size, 255)).lower()


def get_payload(command_name, id, args=None):
    idx = command_indexes[command_name]
    command = dict(transport=dict(attrs=["request", "twoway"], id=id),
                   data=dict(command=dict(idx=idx, name=command_name)))
    if args is not None:
        command['data']['command']['args'] = args

    command_payload = json.dumps(command).strip().replace(" ", "") + ";"
    command_checksum = get_checksum(command_payload)
    return command_checksum, command_payload
