//! Contrat jetable de l'atelier, sans rapport avec le produit.
pub fn etiquette(nombre: u32, prefixe: &str) -> String {
    format!("{prefixe}-{nombre}")
}
