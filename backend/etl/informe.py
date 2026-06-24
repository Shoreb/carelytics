"""
Módulo de trazabilidad de transformaciones ETL.

Registra cada modificación hecha a los datos clínicos de forma auditaable:
qué campo se cambió, en qué paciente, el valor original, el valor nuevo
y la razón técnica. El objetivo es que el médico o analista pueda revisar
exactamente qué tocó el sistema, sin que ningún cambio sea silencioso.
"""

from collections import defaultdict


# Etiquetas legibles por razón de cambio (para el reporte al usuario)
RAZONES = {
    'texto_a_nulo':                 'Texto no numérico convertido a nulo',
    'texto_a_numero_cualitativo':   'Texto cualitativo convertido al valor numérico representativo del rango',
    'atipico_a_nulo':               'Valor fuera de rango clínico convertido a nulo',
    'imputacion_mediana':           'Nulo imputado con la mediana del campo',
    'imputacion_moda':              'Nulo imputado con la moda del campo',
    'imputacion_media':             'Nulo imputado con la media del campo',
    'imputacion_default':           'Nulo imputado con valor por defecto del sistema',
    'ortografia':                   'Error ortográfico corregido a término estándar',
    'normalizacion_sexo':           'Valor normalizado al vocabulario de sexo del sistema',
    'normalizacion_activ':          'Valor normalizado al vocabulario de actividad física',
    'normalizacion_bool':           'Valor convertido a booleano',
}


class InformeLimpieza:
    """
    Acumula todos los cambios realizados durante el ETL y
    genera un reporte estructurado para auditoría médica.

    Uso:
        informe = InformeLimpieza()
        informe.registrar(id_pac='123', campo='glucosa',
                          original=999, nuevo=90.0, razon='atipico_a_nulo')
        resumen = informe.resumen()
    """

    def __init__(self):
        # Lista plana de todos los cambios individuales
        self._cambios = []
        # Contadores por razón para el resumen ejecutivo
        self._contadores = defaultdict(int)

    def registrar(self, id_pac, campo, original, nuevo, razon):
        """Registra un cambio individual. Solo registra si el valor realmente cambió."""
        # Normalizar para comparación (evitar falsos positivos por tipo float vs int)
        try:
            orig_str = str(round(float(original), 4)) if original is not None else 'None'
        except (TypeError, ValueError):
            orig_str = str(original)
        try:
            nuevo_str = str(round(float(nuevo), 4)) if nuevo is not None else 'None'
        except (TypeError, ValueError):
            nuevo_str = str(nuevo)

        if orig_str == nuevo_str:
            return  # Sin cambio real, no registrar

        self._cambios.append({
            'id_paciente': str(id_pac),
            'campo': campo,
            'valor_original': str(original),
            'valor_nuevo': str(nuevo) if nuevo is not None else 'null (será imputado)',
            'razon': razon,
            'razon_legible': RAZONES.get(razon, razon),
        })
        self._contadores[razon] += 1

    def registrar_lote(self, serie_original, serie_nueva, campo, razon, ids):
        """
        Registra cambios en bloque comparando dos Series de pandas.
        Más eficiente que llamar registrar() fila por fila.
        """
        import pandas as pd
        for idx, (orig, nuevo) in enumerate(zip(serie_original, serie_nueva)):
            id_pac = ids.iloc[idx] if hasattr(ids, 'iloc') else ids[idx]
            self.registrar(id_pac, campo, orig, nuevo, razon)

    def total_cambios(self):
        return len(self._cambios)

    def resumen(self):
        """
        Genera el diccionario de resumen que irá en la respuesta del ETL.
        Incluye:
        - total_modificaciones: número total de valores cambiados
        - por_razon: desglose por tipo de cambio
        - por_campo: qué campos fueron más modificados
        - cambios_detalle: primeros 200 cambios individuales (para no sobresaturar)
        - nota: aclaración al usuario sobre la política de cambios
        """
        if not self._cambios:
            return {
                'total_modificaciones': 0,
                'mensaje': 'No se realizaron modificaciones a los datos clínicos.',
                'por_razon': {},
                'por_campo': {},
                'cambios_detalle': [],
            }

        # Agrupación por campo
        por_campo = defaultdict(int)
        for c in self._cambios:
            por_campo[c['campo']] += 1

        # Razones con etiqueta legible
        por_razon = {
            RAZONES.get(r, r): n
            for r, n in self._contadores.items()
        }

        return {
            'total_modificaciones': len(self._cambios),
            'nota': (
                'El sistema realizó las siguientes transformaciones técnicas para garantizar '
                'la compatibilidad de los datos con la base de datos clínica. '
                'Ningún valor fue modificado por criterio diagnóstico — solo por necesidad '
                'técnica (tipos de dato, campos obligatorios). '
                'El criterio clínico sobre si estos valores son correctos corresponde al médico tratante.'
            ),
            'por_razon': dict(sorted(por_razon.items(), key=lambda x: x[1], reverse=True)),
            'por_campo': dict(sorted(por_campo.items(), key=lambda x: x[1], reverse=True)),
            'cambios_detalle': self._cambios[:200],  # Máximo 200 para no saturar la respuesta
            'cambios_truncados': len(self._cambios) > 200,
        }