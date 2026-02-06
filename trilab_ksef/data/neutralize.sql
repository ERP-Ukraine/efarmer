-- noinspection SqlWithoutWhere
UPDATE res_company
SET x_ksef_token                                  = NULL,
    x_ksef_verification_link_private_key_password = NULL,
    x_ksef_verification_link_private_key_datas    = NULL,
    x_ksef_verification_link_certificate_datas    = NULL;

DELETE
FROM ir_config_parameter
WHERE key LIKE 'x_ksef_%_auth_state';
