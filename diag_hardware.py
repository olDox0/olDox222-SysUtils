# diag_hardware.py
import sys
import traceback

print("=== DIAGNÓSTICO DO HARDWAREMONITOR ===")

try:
    from HardwareMonitor.Hardware import Computer, IVisitor, IComputer, IHardware, ISensor, IParameter
    print("[OK] Importação da biblioteca HardwareMonitor bem-sucedida.")
except ImportError as e:
    print(f"[ERRO FATAL] Biblioteca não encontrada: {e}")
    sys.exit(1)

class UpdateVisitor(IVisitor):
    __namespace__ = "SysUtilsDiag"
    def VisitComputer(self, computer: IComputer):
        computer.Traverse(self)
    def VisitHardware(self, hardware: IHardware):
        hardware.Update()
        for subHardware in hardware.SubHardware:
            subHardware.Update()
    def VisitSensor(self, sensor: ISensor):
        pass
    def VisitParameter(self, parameter: IParameter):
        pass

try:
    print("[*] Inicializando Computer()...")
    comp = Computer()
    
    # Habilita TUDO para o diagnóstico
    comp.IsCpuEnabled = True
    comp.IsGpuEnabled = True
    comp.IsMotherboardEnabled = True
    comp.IsBatteryEnabled = True
    comp.IsMemoryEnabled = True
    
    comp.Open()
    print("[OK] Computer.Open() bem-sucedido.")
    
    print("[*] Atualizando sensores (Aceitando Visitor)...")
    comp.Accept(UpdateVisitor())
    print("[OK] Sensores atualizados.")
    
    print("\n=== HARDWARES E SENSORES ENCONTRADOS ===")
    hw_count = 0
    for hw in comp.Hardware:
        hw_count += 1
        print(f"\n[Hardware] {hw.Name} (Tipo: {hw.HardwareType})")
        
        # Se houver sub-hardwares (ex: núcleos da CPU)
        for sub in hw.SubHardware:
            print(f"  [Sub-Hardware] {sub.Name} (Tipo: {sub.HardwareType})")

        # Listar sensores
        for sensor in hw.Sensors:
            print(f"  • Sensor: {sensor.Name}")
            print(f"    Tipo: {sensor.SensorType} | Valor: {sensor.Value}")
            
    if hw_count == 0:
        print("[AVISO] Nenhum hardware foi encontrado pela biblioteca.")
        
    comp.Close()
    print("\n[FIM] Diagnóstico concluído.")

except Exception as e:
    print("\n[ERRO FATAL] Falha durante a execução do HardwareMonitor:")
    traceback.print_exc()