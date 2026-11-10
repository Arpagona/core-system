//! Contrat jetable de l'atelier, sans rapport avec le produit.
pub fn etiquette(nombre: u32) -> String {
    format!("atelier-{nombre}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn etiquette_reste_stable() {
        assert_eq!(etiquette(3), "atelier-3");
    }
}
