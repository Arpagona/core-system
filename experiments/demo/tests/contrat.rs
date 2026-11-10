#[test]
fn consommateur_respecte_le_contrat() {
    assert_eq!(atelier_demo::message(), "atelier-7");
    assert_eq!(atelier_contrat::etiquette(0, "atelier"), "atelier-0");
}

#[test]
fn prefixe_est_transmis_au_contrat() {
    assert_eq!(atelier_contrat::etiquette(4, "scenario"), "scenario-4");
}
