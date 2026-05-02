"""
Módulo para generación de XML de nómina electrónica DIAN según resolución 000013

Genera documentos XML compliant con el esquema XSD de la DIAN para nómina electrónica,
incluyendo:
- Nómina individual
- Nómina de ajuste
- Notas de eliminación
- Firma electrónica (preparación para XMLDSIG)

Validaciones según especificaciones técnicas DIAN 2023-2024.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any
from lxml import etree
import uuid


class TipoDocumento(str, Enum):
    """Tipos de documento de identidad válidos para nómina electrónica"""
    CEDULA_CIUDADANIA = "13"
    CEDULA_EXTRANJERIA = "22"
    NIT = "31"
    TARJETA_EXTRANJERIA = "21"
    PASAPORTE = "41"
    DOCUMENTO_EXTRANJERO = "42"
    PEP = "47"  # Permiso Especial de Permanencia


class TipoNota(str, Enum):
    """Tipos de nota para nómina electrónica"""
    REEMPLAZAR = "1"  # Reemplaza documento previo
    ELIMINAR = "2"    # Elimina documento previo


class TipoTrabajador(str, Enum):
    """Tipos de trabajador según contrato"""
    EMPLEADO = "00"
    OBRERO = "01"
    CONTRATISTA = "02"
    PENSIONADO = "03"
    APRENDIZ = "04"
    PRACTICANTE = "05"


class SubtipoTrabajador(str, Enum):
    """Subtipos de trabajador"""
    DEPENDIENTE = "00"
    INTEGRAL = "01"


class TipoPeriodo(str, Enum):
    """Períodos de nómina"""
    SEMANAL = "1"
    DECENAL = "2"
    CATORCENAL = "3"
    QUINCENAL = "4"
    MENSUAL = "5"


@dataclass
class Empleador:
    """Información del empleador para XML DIAN"""
    nit: str
    dv: str
    razon_social: str
    primer_apellido: Optional[str] = None
    segundo_apellido: Optional[str] = None
    primer_nombre: Optional[str] = None
    otros_nombres: Optional[str] = None
    pais: str = "CO"
    departamento: str = ""
    municipio: str = ""
    direccion: str = ""
    
    def __post_init__(self):
        """Valida formato NIT"""
        if not self.nit.isdigit():
            raise ValueError(f"NIT debe contener solo dígitos: {self.nit}")
        if len(self.nit) < 8 or len(self.nit) > 10:
            raise ValueError(f"NIT debe tener entre 8 y 10 dígitos: {self.nit}")


@dataclass
class Trabajador:
    """Información del trabajador para XML DIAN"""
    tipo_documento: TipoDocumento
    numero_documento: str
    primer_apellido: str
    primer_nombre: str
    segundo_apellido: Optional[str] = None
    otros_nombres: Optional[str] = None
    pais: str = "CO"
    departamento: str = ""
    municipio: str = ""
    direccion: str = ""
    codigo_trabajador: Optional[str] = None
    tipo_trabajador: TipoTrabajador = TipoTrabador.EMPLEADO
    subtipo_trabajador: SubtipoTrabajador = SubtipoTrabajador.DEPENDIENTE
    alto_riesgo: bool = False
    salario_integral: bool = False
    
    def __post_init__(self):
        """Valida documento según tipo"""
        if self.tipo_documento == TipoDocumento.NIT:
            if not self.numero_documento.isdigit():
                raise ValueError("NIT debe contener solo dígitos")
        
        if self.salario_integral:
            self.subtipo_trabajador = SubtipoTrabajador.INTEGRAL


@dataclass
class Devengado:
    """Conceptos devengados (ingresos) del trabajador"""
    basico: Decimal = Decimal("0")
    auxilio_transporte: Decimal = Decimal("0")
    horas_extras: Decimal = Decimal("0")
    recargos: Decimal = Decimal("0")
    comisiones: Decimal = Decimal("0")
    bonificaciones: Decimal = Decimal("0")
    viatiticos: Decimal = Decimal("0")
    vacaciones_comunes: Decimal = Decimal("0")
    vacaciones_compensadas: Decimal = Decimal("0")
    primas: Decimal = Decimal("0")
    cesantias: Decimal = Decimal("0")
    intereses_cesantias: Decimal = Decimal("0")
    incapacidades: Decimal = Decimal("0")
    licencias_maternidad: Decimal = Decimal("0")
    licencias_paternidad: Decimal = Decimal("0")
    otros_conceptos: Dict[str, Decimal] = field(default_factory=dict)
    
    def total(self) -> Decimal:
        """Calcula el total de devengados"""
        total = (
            self.basico + self.auxilio_transporte + self.horas_extras +
            self.recargos + self.comisiones + self.bonificaciones +
            self.viatiticos + self.vacaciones_comunes + self.vacaciones_compensadas +
            self.primas + self.cesantias + self.intereses_cesantias +
            self.incapacidades + self.licencias_maternidad + self.licencias_paternidad
        )
        
        for valor in self.otros_conceptos.values():
            total += valor
            
        return total


@dataclass
class Deduccion:
    """Conceptos deducidos (descuentos) del trabajador"""
    salud: Decimal = Decimal("0")
    pension: Decimal = Decimal("0")
    fondo_solidaridad: Decimal = Decimal("0")
    fondo_subsistencia: Decimal = Decimal("0")
    retencion_fuente: Decimal = Decimal("0")
    sindicatos: Decimal = Decimal("0")
    sanciones: Decimal = Decimal("0")
    libranzas: Decimal = Decimal("0")
    embargos: Decimal = Decimal("0")
    anticipos: Decimal = Decimal("0")
    otras_deducciones: Dict[str, Decimal] = field(default_factory=dict)
    
    def total(self) -> Decimal:
        """Calcula el total de deducciones"""
        total = (
            self.salud + self.pension + self.fondo_solidaridad +
            self.fondo_subsistencia + self.retencion_fuente +
            self.sindicatos + self.sanciones + self.libranzas +
            self.embargos + self.anticipos
        )
        
        for valor in self.otras_deducciones.values():
            total += valor
            
        return total


@dataclass
class PeriodoNomina:
    """Período de la nómina"""
    fecha_inicio: date
    fecha_fin: date
    tipo_periodo: TipoPeriodo
    fecha_pago: date
    
    def __post_init__(self):
        """Valida fechas del período"""
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("Fecha fin no puede ser anterior a fecha inicio")
        if self.fecha_pago < self.fecha_fin:
            raise ValueError("Fecha de pago no puede ser anterior a fecha fin del período")


@dataclass
class DocumentoNomina:
    """Documento de nómina electrónica completo"""
    # Identificación del documento
    numero: str
    prefijo: str = ""
    cune: Optional[str] = None  # Se genera automáticamente
    
    # Fechas y período
    fecha_emision: datetime = field(default_factory=datetime.now)
    periodo: Optional[PeriodoNomina] = None
    
    # Partes
    empleador: Optional[Empleador] = None
    trabajador: Optional[Trabajador] = None
    
    # Liquidación
    devengados: Devengado = field(default_factory=Devengado)
    deducciones: Deduccion = field(default_factory=Deduccion)
    
    # Notas
    notas: List[str] = field(default_factory=list)
    
    # Para notas de ajuste o eliminación
    es_nota: bool = False
    tipo_nota: Optional[TipoNota] = None
    documento_referencia: Optional[str] = None
    cune_referencia: Optional[str] = None
    
    def __post_init__(self):
        """Validaciones del documento"""
        if self.es_nota and not self.tipo_nota:
            raise ValueError("Debe especificar tipo de nota")
        
        if self.es_nota and not self.documento_referencia:
            raise ValueError("Nota debe referenciar documento original")
    
    def neto_pagar(self) -> Decimal:
        """Calcula el neto a pagar (devengado - deducido)"""
        return self.devengados.total() - self.deducciones.total()
    
    def generar_cune(self, clave_tecnica: str = "") -> str:
        """
        Genera el CUNE (Código Único de Nómina Electrónica)
        
        CUNE = SHA384(NumNIE + FecNIE + HorNIE + ValDev + ValDed + ValTol + NitOFE + NumDocEmp + ClvTec + TipoAmb)
        
        Args:
            clave_tecnica: Clave técnica asignada por DIAN
        """
        import hashlib
        
        if not self.empleador or not self.trabajador or not self.periodo:
            raise ValueError("Faltan datos para generar CUNE")
        
        # Formatear valores según especificación DIAN
        num_nie = f"{self.prefijo}{self.numero}"
        fec_nie = self.fecha_emision.strftime("%Y-%m-%d")
        hor_nie = self.fecha_emision.strftime("%H:%M:%S-05:00")  # Zona horaria Colombia
        val_dev = f"{self.devengados.total():.2f}"
        val_ded = f"{self.deducciones.total():.2f}"
        val_tol = f"{self.neto_pagar():.2f}"
        nit_ofe = self.empleador.nit
        num_doc_emp = self.trabajador.numero_documento
        tipo_amb = "2"  # 1=Producción, 2=Habilitación
        
        # Concatenar según especificación
        cadena = (
            f"{num_nie}{fec_nie}{hor_nie}{val_dev}{val_ded}{val_tol}"
            f"{nit_ofe}{num_doc_emp}{clave_tecnica}{tipo_amb}"
        )
        
        # Generar hash SHA384
        hash_obj = hashlib.sha384(cadena.encode('utf-8'))
        cune = hash_obj.hexdigest()
        
        self.cune = cune
        return cune


class GeneradorXMLDIAN:
    """Generador de XML de nómina electrónica según especificaciones DIAN"""
    
    # Namespaces oficiales DIAN
    NAMESPACES = {
        None: "dian:gov:co:facturaelectronica:NominaIndividual",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xsd": "http://www.w3.org/2001/XMLSchema",
        "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    }
    
    def __init__(self, ambiente: str = "2"):
        """
        Inicializa el generador
        
        Args:
            ambiente: "1" para producción, "2" para habilitación
        """
        self.ambiente = ambiente
    
    def _crear_elemento(self, tag: str, texto: Optional[str] = None, 
                       atributos: Optional[Dict[str, str]] = None) -> etree.Element:
        """Crea un elemento XML con namespace"""
        elem = etree.Element(tag, nsmap=self.NAMESPACES)
        if texto is not None:
            elem.text = str(texto)
        if atributos:
            for key, value in atributos.items():
                elem.set(key, value)
        return elem
    
    def _agregar_informacion_general(self, root: etree.Element, doc: DocumentoNomina) -> None:
        """Agrega la sección InformacionGeneral del XML"""
        info = etree.SubElement(root, "InformacionGeneral")
        
        # Versión del formato
        etree.SubElement(info, "Version").text = "V1.0: Documento Soporte de Pago de Nómina Electrónica"
        
        # Ambiente
        etree.SubElement(info, "Ambiente").text = self.ambiente
        
        # Tipo de XML
        if doc.es_nota:
            etree.SubElement(info, "TipoXML").text = "103"  # Nota de ajuste
        else:
            etree.SubElement(info, "TipoXML").text = "102"  # Nómina individual
        
        # Identificadores
        if doc.prefijo:
            etree.SubElement(info, "Prefijo").text = doc.prefijo
        etree.SubElement(info, "Consecutivo").text = doc.numero
        
        # Fecha generación
        etree.SubElement(info, "FechaGen").text = doc.fecha_emision.strftime("%Y-%m-%d")
        etree.SubElement(info, "HoraGen").text = doc.fecha_emision.strftime("%H:%M:%S-05:00")
        
        # Período
        if doc.periodo:
            periodo_elem = etree.SubElement(info, "PeriodoNomina")
            etree.SubElement(periodo_elem, "FechaIngreso").text = doc.periodo.fecha_inicio.strftime("%Y-%m-%d")
            etree.SubElement(periodo_elem, "FechaLiquidacionInicio").text = doc.periodo.fecha_inicio.strftime("%Y-%m-%d")
            etree.SubElement(periodo_elem, "FechaLiquidacionFin").text = doc.periodo.fecha_fin.strftime("%Y-%m-%d")
            etree.SubElement(periodo_elem, "TiempoLaborado").text = str((doc.periodo.fecha_fin - doc.periodo.fecha_inicio).days + 1)
            etree.SubElement(periodo_elem, "FechaGen").text = doc.periodo.fecha_pago.strftime("%Y-%m-%d")
        
        # Moneda (siempre COP para Colombia)
        etree.SubElement(info, "TipoMoneda").text = "COP"
        
        # CUNE
        if doc.cune:
            etree.SubElement(info, "CUNE").text = doc.cune
        
        # Información de nota si aplica
        if doc.es_nota:
            nota_elem = etree.SubElement(info, "InformacionNota")
            etree.SubElement(nota_elem, "Tipo").text = doc.tipo_nota.value
            if doc.documento_referencia:
                etree.SubElement(nota_elem, "NumeroDocumento").text = doc.documento_referencia
            if doc.cune_referencia:
                etree.SubElement(nota_elem, "CUNE").text = doc.cune_referencia
    
    def _agregar_empleador(self, root: etree.Element, empleador: Empleador) -> None:
        """Agrega la sección Empleador del XML"""
        emp = etree.SubElement(root, "Empleador")
        
        # Identificación
        etree.SubElement(emp, "TipoDocumento").text = TipoDocumento.NIT.value
        etree.SubElement(emp, "NumeroDocumento").text = empleador.nit
        etree.SubElement(emp, "DV").text = empleador.dv
        
        # Razón social o nombres
        if empleador.razon_social:
            etree.SubElement(emp, "RazonSocial").text = empleador.razon_social
        else:
            if empleador.primer_apellido:
                etree.SubElement(emp, "PrimerApellido").text = empleador.primer_apellido
            if empleador.segundo_apellido:
                etree.SubElement(emp, "SegundoApellido").text = empleador.segundo_apellido
            if empleador.primer_nombre:
                etree.SubElement(emp, "PrimerNombre").text = empleador.primer_nombre
            if empleador.otros_nombres:
                etree.SubElement(emp, "OtrosNombres").text = empleador.otros_nombres
        
        # Ubicación
        etree.SubElement(emp, "Pais").text = empleador.pais
        if empleador.departamento:
            etree.SubElement(emp, "DepartamentoEstado").text = empleador.departamento
        if empleador.municipio:
            etree.SubElement(emp, "MunicipioCiudad").text = empleador.municipio
        if empleador.direccion:
            etree.SubElement(emp, "Direccion").text = empleador.direccion
    
    def _agregar_trabajador(self, root: etree.Element, trabajador: Trabajador) -> None:
        """Agrega la sección Trabajador del XML"""
        trab = etree.SubElement(root, "Trabajador")
        
        # Identificación
        etree.SubElement(trab, "TipoTrabajador").text = trabajador.tipo_trabajador.value
        etree.SubElement(trab, "SubTipoTrabajador").text = trabajador.subtipo_trabajador.value
        etree.SubElement(trab, "AltoRiesgoPension").text = "true" if trabajador.alto_riesgo else "false"
        
        etree.SubElement(trab, "TipoDocumento").text = trabajador.tipo_documento.value
        etree.SubElement(trab, "NumeroDocumento").text = trabajador.numero_documento
        
        # Nombres
        etree.SubElement(trab, "PrimerApellido").text = trabajador.primer_apellido
        if trabajador.segundo_apellido:
            etree.SubElement(trab, "SegundoApellido").text = trabajador.segundo_apellido
        etree.SubElement(trab, "PrimerNombre").text = trabajador.primer_nombre
        if trabajador.otros_nombres:
            etree.SubElement(trab, "OtrosNombres").text = trabajador.otros_nombres
        
        # Ubicación
        etree.SubElement(trab, "Pais").text = trabajador.pais
        if trabajador.departamento:
            etree.SubElement(trab, "DepartamentoEstado").text = trabajador.departamento
        if trabajador.municipio:
            etree.SubElement(trab, "MunicipioCiudad").text = trabajador.municipio
        if trabajador.direccion:
            etree.SubElement(trab, "Direccion").text = trabajador.direccion
        
        # Código trabajador
        if trabajador.codigo_trabajador:
            etree.SubElement(trab, "CodigoTrabajador").text = trabajador.codigo_trabajador
        
        # Salario integral
        etree.SubElement(trab, "SalarioIntegral").text = "true" if trabajador.salario_integral else "false"
    
    def _agregar_devengados(self, root: etree.Element, devengados: Devengado) -> None:
        """Agrega la sección Devengados del XML"""
        if devengados.total() == 0:
            return
        
        dev = etree.SubElement(root, "Devengados")
        
        # Básico
        if devengados.basico > 0:
            basico = etree.SubElement(dev, "Basico")
            etree.SubElement(basico, "DiasTrabajados").text = "30"  # Ajustar según período
            etree.SubElement(basico, "SueldoTrabajado").text = f"{devengados.basico:.2f}"
        
        # Transporte
        if devengados.auxilio_transporte > 0:
            transporte = etree.SubElement(dev, "Transporte")
            etree.SubElement(transporte, "AuxilioTransporte").text = f"{devengados.auxilio_transporte:.2f}"
        
        # Horas extras y recargos
        if devengados.horas_extras > 0:
            he = etree.SubElement(dev, "HorasExtras")
            etree.SubElement(he, "Cantidad").text = "0"
            etree.SubElement(he, "Pago").text = f"{devengados.horas_extras:.2f}"
        
        # Vacaciones
        if devengados.vacaciones_comunes > 0:
            vac = etree.SubElement(dev, "Vacaciones")
            vacaciones_comunes = etree.SubElement(vac, "VacacionesComunes")
            etree.SubElement(vacaciones_comunes, "Cantidad").text = "0"
            etree.SubElement(vacaciones_comunes, "Pago").text = f"{devengados.vacaciones_comunes:.2f}"
        
        if devengados.vacaciones_compensadas > 0:
            if devengados.vacaciones_comunes == 0:
                vac = etree.SubElement(dev, "Vacaciones")
            vacaciones_comp = etree.SubElement(vac, "VacacionesCompensadas")
            etree.SubElement(vacaciones_comp, "Cantidad").text = "0"
            etree.SubElement(vacaciones_comp, "Pago").text = f"{devengados.vacaciones_compensadas:.2f}"
        
        # Primas
        if devengados.primas > 0:
            prima = etree.SubElement(dev, "Primas")
            etree.SubElement(prima, "Cantidad").text = "0"
            etree.SubElement(prima, "Pago").text = f"{devengados.primas:.2f}"
            etree.SubElement(prima, "PagoNS").text = "0.00"
        
        # Cesantías
        if devengados.cesantias > 0:
            ces = etree.SubElement(dev, "Cesantias")
            etree.SubElement(ces, "Pago").text = f"{devengados.cesantias:.2f}"
            etree.SubElement(ces, "Porcentaje").text = "8.33"
            etree.SubElement(ces, "PagoIntereses").text = f"{devengados.intereses_cesantias:.2f}"
        
        # Incapacidades
        if devengados.incapacidades > 0:
            incap = etree.SubElement(dev, "Incapacidades")
            incapacidad = etree.SubElement(incap, "Incapacidad")
            etree.SubElement(incapacidad, "Tipo").text = "1"  # Común
            etree.SubElement(incapacidad, "Cantidad").text = "0"
            etree.SubElement(incapacidad, "Pago").text = f"{devengados.incapacidades:.2f}"
        
        # Licencias
        if devengados.licencias_maternidad > 0:
            lic = etree.SubElement(dev, "Licencias")
            licencia_mat = etree.SubElement(lic, "LicenciaMaternidad")
            etree.SubElement(licencia_mat, "Cantidad").text = "0"
            etree.SubElement(licencia_mat, "Pago").text = f"{devengados.licencias_maternidad:.2f}"
        
        if devengados.licencias_paternidad > 0:
            if devengados.licencias_maternidad == 0:
                lic = etree.SubElement(dev, "Licencias")
            licencia_pat = etree.SubElement(lic, "LicenciaPaternidad")
            etree.SubElement(licencia_pat, "Cantidad").text = "0"
            etree.SubElement(licencia_pat, "Pago").text = f"{devengados.licencias_paternidad:.2f}"
        
        # Bonificaciones
        if devengados.bonificaciones > 0:
            bonif = etree.SubElement(dev, "Bonificaciones")
            etree.SubElement(bonif, "BonificacionS").text = f"{devengados.bonificaciones:.2f}"
        
        # Comisiones
        if devengados.comisiones > 0:
            comis = etree.SubElement(dev, "Comisiones")
            etree.SubElement(comis, "Comision").text = f"{devengados.comisiones:.2f}"
        
        # Otros conceptos
        if devengados.otros_conceptos:
            otros = etree.SubElement(dev, "OtrosConceptos")
            for concepto, valor in devengados.otros_conceptos.items():
                otro = etree.SubElement(otros, "OtroConcepto")
                etree.SubElement(otro, "DescripcionConcepto").text = concepto
                etree.SubElement(otro, "ConceptoS").text = f"{valor:.2f}"
    
    def _agregar_deducciones(self, root: etree.Element, deducciones: Deduccion) -> None:
        """Agrega la sección Deducciones del XML"""
        if deducciones.total() == 0:
            return
        
        ded = etree.SubElement(root, "Deducciones")
        
        # Salud
        if deducciones.salud > 0:
            salud = etree.SubElement(ded, "Salud")
            etree.SubElement(salud, "Porcentaje").text = "4.00"
            etree.SubElement(salud, "Deduccion").text = f"{deducciones.salud:.2f}"
        
        # Pensión
        if deducciones.pension > 0:
            pension = etree.SubElement(ded, "FondoPension")
            etree.SubElement(pension, "Porcentaje").text = "4.00"
            etree.SubElement(pension, "Deduccion").text = f"{deducciones.pension:.2f}"
        
        # Fondo de Solidaridad Pensional
        if deducciones.fondo_solidaridad > 0:
            fsp = etree.SubElement(ded, "FondoSP")
            etree.SubElement(fsp, "Porcentaje").text = "1.00"
            etree.SubElement(fsp, "DeduccionSP").text = f"{deducciones.fondo_solidaridad:.2f}"
            if deducciones.fondo_subsistencia > 0:
                etree.SubElement(fsp, "PorcentajeSub").text = "0.20"
                etree.SubElement(fsp, "DeduccionSub").text = f"{deducciones.fondo_subsistencia:.2f}"
        
        # Retención en la fuente
        if deducciones.retencion_fuente > 0:
            retencion = etree.SubElement(ded, "Retencion")
            etree.SubElement(retencion, "Porcentaje").text = "0.00"
            etree.SubElement(retencion, "Deduccion").text = f"{deducciones.retencion_fuente:.2f}"
        
        # Sindicatos
        if deducciones.sindicatos > 0:
            sindicato = etree.SubElement(ded, "Sindicatos")
            etree.SubElement(sindicato, "Porcentaje").text = "0.00"
            etree.SubElement(sindicato, "Deduccion").text = f"{deducciones.sindicatos:.2f}"
        
        # Sanciones
        if deducciones.sanciones > 0:
            sancion = etree.SubElement(ded, "Sanciones")
            etree.SubElement(sancion, "SancionPublic").text = f"{deducciones.sanciones:.2f}"
        
        # Libranzas
        if deducciones.libranzas > 0:
            libranza = etree.SubElement(ded, "Libranzas")
            etree.SubElement(libranza, "Descripcion").text = "Libranza"
            etree.SubElement(libranza, "Deduccion").text = f"{deducciones.libranzas:.2f}"
        
        # Otras deducciones
        if deducciones.otras_deducciones:
            otras = etree.SubElement(ded, "OtrasDeducciones")
            for concepto, valor in deducciones.otras_deducciones.items():
                otra = etree.SubElement(otras, "OtraDeduccion")
                etree.SubElement(otra, "Descripcion").text = concepto
                etree.SubElement(otra, "Deduccion").text = f"{valor:.2f}"
    
    def generar(self, documento: DocumentoNomina) -> str:
        """
        Genera el XML de nómina electrónica completo
        
        Args:
            documento: Documento de nómina a serializar
            
        Returns:
            String con el XML generado
        """
        # Validar datos requeridos
        if not documento.empleador:
            raise ValueError("Debe proporcionar información del empleador")
        if not documento.trabajador:
            raise ValueError("Debe proporcionar información del trabajador")
        if not documento.periodo:
            raise ValueError("Debe proporcionar período de nómina")
        
        # Crear elemento raíz
        root = self._crear_elemento("NominaIndividual")
        root.set("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation",
                "dian:gov:co:facturaelectronica:NominaIndividual NominaIndividualElectronicaXSD.xsd")
        
        # Agregar secciones
        self._agregar_informacion_general(root, documento)
        self._agregar_empleador(root, documento.empleador)
        self._agregar_trabajador(root, documento.trabajador)
        
        # Pago
        pago = etree.SubElement(root, "Pago")
        etree.SubElement(pago, "Forma").text = "1"  # Contado
        etree.SubElement(pago, "Metodo").text = "10"  # Efectivo (ajustar según caso)