# Screening de calibração RVC 01

Amostra de 84 ocorrências, duas por consulta, selecionadas entre registros com resumo em posições aproximadamente 1/3 e 2/3 dentro de cada conjunto da consulta. A decisão foi tomada sem exibir a identificação da query durante a leitura. Como a exportação está ordenada e a amostra é sistemática, estes percentuais são diagnósticos de calibração, não estimativas inferenciais de precisão.

## Resultado geral

- Incluídos: **65/84 (77.4%)**
- Excluídos: **10/84 (11.9%)**
- Dúvida: **9/84 (10.7%)**

## Por família

| Família | n | Incluir | Excluir | Dúvida |
|---|---:|---:|---:|---:|
| lexical | 32 | 20 | 7 | 5 |
| semantic | 32 | 28 | 3 | 1 |
| adversarial | 20 | 17 | 0 | 3 |

## Por consulta

| Consulta | Incluir | Excluir | Dúvida |
|---|---:|---:|---:|
| rvc_a01_compact_city_negative_null | 2 | 0 | 0 |
| rvc_a02_vacant_land_positive_functions | 2 | 0 | 0 |
| rvc_a03_capacity_without_outcomes | 0 | 0 | 2 |
| rvc_a04_fragmentation_can_help | 1 | 0 | 1 |
| rvc_a05_digitalization_new_burdens | 2 | 0 | 0 |
| rvc_a06_coercive_land_policy_unintended | 2 | 0 | 0 |
| rvc_a07_regeneration_displacement | 2 | 0 | 0 |
| rvc_a08_more_capacity_not_solution | 2 | 0 | 0 |
| rvc_a09_land_reuse_not_best_option | 2 | 0 | 0 |
| rvc_a10_value_capture_limits | 2 | 0 | 0 |
| rvc_l01_urban_vacancy_underuse | 1 | 1 | 0 |
| rvc_l02_inner_city_reuse_regeneration | 1 | 1 | 0 |
| rvc_l03_brownfield_land_redevelopment | 1 | 0 | 1 |
| rvc_l04_densification_compact_city_outcomes | 2 | 0 | 0 |
| rvc_l05_sprawl_containment_infill | 1 | 0 | 1 |
| rvc_l06_land_activation_compulsory_development | 1 | 1 | 0 |
| rvc_l07_peuc_funcao_social | 2 | 0 | 0 |
| rvc_l08_land_policy_implementation | 1 | 1 | 0 |
| rvc_l09_policy_state_institutional_capacity_local | 1 | 0 | 1 |
| rvc_l10_interorganizational_coordination_urban | 2 | 0 | 0 |
| rvc_l11_institutional_fit_scale_authority | 2 | 0 | 0 |
| rvc_l12_digital_planning_gis_automation | 1 | 0 | 1 |
| rvc_l13_administrative_burden_process_design | 0 | 1 | 1 |
| rvc_l14_value_capture_public_value_equity | 2 | 0 | 0 |
| rvc_l15_adaptive_reuse_local_government | 0 | 2 | 0 |
| rvc_l16_urban_regeneration_governance_capacity | 2 | 0 | 0 |
| rvc_s01_norm_to_implementation | 2 | 0 | 0 |
| rvc_s02_resources_to_recurring_action | 2 | 0 | 0 |
| rvc_s03_interface_bottlenecks | 2 | 0 | 0 |
| rvc_s04_removable_burden_process_design | 0 | 2 | 0 |
| rvc_s05_external_capacity_absorption | 2 | 0 | 0 |
| rvc_s06_underused_land_public_value | 1 | 0 | 1 |
| rvc_s07_coercion_vs_enablement | 2 | 0 | 0 |
| rvc_s08_automation_human_judgment | 1 | 1 | 0 |
| rvc_s09_vacancy_to_intervention_chain | 2 | 0 | 0 |
| rvc_s10_priority_vs_readiness | 2 | 0 | 0 |
| rvc_s11_spatial_institutional_fit | 2 | 0 | 0 |
| rvc_s12_capacity_performance_results | 2 | 0 | 0 |
| rvc_s13_land_policy_capacity_bridge | 2 | 0 | 0 |
| rvc_s14_regeneration_distributional_safeguards | 2 | 0 | 0 |
| rvc_s15_land_value_creation_capture_governance | 2 | 0 | 0 |
| rvc_s16_institutional_learning_continuity | 2 | 0 | 0 |

## Observações de calibração

- A amostra confirmou falsos positivos lexicais inequívocos em algumas consultas: química orgânica em `rvc_l02`, geotermia em `rvc_l08`, protestos em rede em `rvc_l13` e retrofit energético em `rvc_l15`.
- As consultas semânticas recuperaram literatura institucional útil, mas também casos transferíveis apenas por analogia; estes foram mantidos como `duvida` quando a utilidade depende de leitura integral.
- As buscas adversariais mostraram boa capacidade de localizar contraevidência diretamente pertinente, sobretudo compacidade, vacância com funções positivas, efeitos não intencionais de coerção e captura de valor.
- Registros repetidos entre consultas receberam decisão consistente; a unidade de screening continua sendo a obra deduplicada.

## Uso no programa

`calibration_01_import.csv` pode ser usado com `import-screening --decision-column decision --reason-column exclusion_reason`. Linhas com decisão vazia correspondem a `duvida` e serão ignoradas pelo importador, preservando-as para revisão humana.
