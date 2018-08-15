#!/usr/bin/env python

#
# File taken from git@github.com:riscv/riscv-opcodes.git
#
#   Modified for use with the SCARV Crypto ISE project.
#
#

import math
import sys
import tokenize

namelist = []
match = {}
mask = {}
pseudos = {}
arguments = {}

cargs= ['imm11'   , 'imm11hi' , 'imm11lo' , 'imm5'
, 'cshamt'  , 'cmshamt' , 'b0'      , 'b1'      ,
'b2'      , 'b3'      , 'ca'      , 'cb'      ,
'cc'      , 'cd'      , 'crs1'    , 'crs2'    ,
'crs3'    , 'crs4'    , 'crd'     , 'crdm'    ,
'lut4'   ]

acodes = {}
acodes['imm11'  ] = "Xl"
acodes['imm11hi'] = "Xm"
acodes['imm11lo'] = "Xn"
acodes['imm5'   ] = "X5"
acodes['cshamt' ] = "XR"
acodes['cmshamt'] = "Xr"
acodes['b0'     ] = "Xw"
acodes['b1'     ] = "Xx"
acodes['b2'     ] = "Xy"
acodes['b3'     ] = "Xz"
acodes['ca'     ] = "Xa"
acodes['cb'     ] = "Xb"
acodes['cc'     ] = "Xc"
acodes['cd'     ] = "Xd"
acodes['crs1'   ] = "Xs"
acodes['crs2'   ] = "Xt"
acodes['crs3'   ] = "XS"
acodes['crs4'   ] = "XT"
acodes['crd'    ] = "XD"
acodes['crdm'   ] = "XM"
acodes['lut4'   ] = "X4"
acodes['rd'     ] = "d"
acodes['rs1'    ] = "s"

arglut = {}
arglut['imm11'  ] = (31,21)
arglut['imm11hi'] = (31,25)
arglut['imm11lo'] = (10, 7)
arglut['imm5'   ] = (19,15)
arglut['cshamt' ] = (23,20)
arglut['cmshamt'] = (27,24)
arglut['b0'     ] = (31,30)
arglut['b1'     ] = (29,28)
arglut['b2'     ] = (27,26)
arglut['b3'     ] = (25,24)
arglut['ca'     ] = (24,24)
arglut['cb'     ] = (19,19)
arglut['cc'     ] = (11,11)
arglut['cd'     ] = (20,20)
arglut['crs1'   ] = (18,15)
arglut['crs2'   ] = (23,20)
arglut['crs3'   ] = (27,24)
arglut['crs4'   ] = (31,28)
arglut['crd'    ] = (10, 7)
arglut['crdm'   ] = ( 9, 7)
arglut['lut4'   ] = (28,25)

arglut['rd'] = (11,7)
arglut['rs1'] = (19,15)
arglut['rs2'] = (24,20)
arglut['rs3'] = (31,27)
arglut['aqrl'] = (26,25)
arglut['fm'] = (31,28)
arglut['pred'] = (27,24)
arglut['succ'] = (23,20)
arglut['rm'] = (14,12)
arglut['imm20'] = (31,12)
arglut['jimm20'] = (31,12)
arglut['imm12'] = (31,20)
arglut['imm12hi'] = (31,25)
arglut['bimm12hi'] = (31,25)
arglut['imm12lo'] = (11,7)
arglut['bimm12lo'] = (11,7)
arglut['zimm'] = (19,15)
arglut['shamt'] = (25,20)
arglut['shamtw'] = (24,20)
arglut['vseglen'] = (31,29)

opcode_base = 0
opcode_size = 7
funct_base = 12
funct_size = 3

def binary(n, digits=0):
  rep = bin(n)[2:]
  return rep if digits == 0 else ('0' * (digits - len(rep))) + rep


def make_c_extra(match,mask):
    """
    Generates extra useful macros and the like for adding instructions
    to binutils and GAS specifically.
    """
    tp = []
    for field in arglut:
        if not field in cargs:
            continue
        # Generate encode/extract macros for each field which can be
        # dumped into riscv-binutils/include/opcode/riscv.h
        enc_name = "ENCODE_X_%s" % (field.upper())
        ext_name = "EXTRACT_X_%s" % (field.upper())
        val_name = "VALIDATE_X_%s" % (field.upper())
        
        fsize = 1 + (arglut[field][0] - arglut[field][1])
        flow  = arglut[field][1]
        fmask = "0b" + ("1"*fsize)

        mname = "OP_MASK_X%s" % field.upper()
        sname = "OP_SH_X%s"   % field.upper()
        
        tp.append("#define %s %s" %(mname, fmask))
        tp.append("#define %s %s" %(sname, flow))
        tp.append("#define %s(X)  ((X &  %s) << %s)" %(
            enc_name,mname,sname))
        tp.append("#define %s(X) ((X >> OP_SH_X%s)  & OP_MASK_X%s)" %(
            ext_name,sname,mname))
        tp.append("#define %s(X) ((%s(X)) == (%s(X)))" %(
            val_name,enc_name,ext_name))
    tp.sort()


    # Generate instruction and argument definitions
    for mnemonic in namelist:
        tw  = ("{\"%s\", " % mnemonic).ljust(15)     # instr name
        tw += "\"x\", "                 # ISA / ISE

        fields = sorted(arguments[mnemonic])
        tw += ("\"%s\", " % ",".join([acodes[f] for f in fields])).ljust(22)

        tw += "MATCH_%s, " %(mnemonic.replace(".","_").upper())
        tw += "MASK_%s, "  %(mnemonic.replace(".","_").upper())
        tw += "match_opcode, 0},"
        
        tp.append(tw)
 
    for l in tp:
        print(l)
    
    # Generate instruction assembly logic
    print("")
    print("case 'X': /* SCARV Crypto ISE */ ")
    print("  switch (*++args){")

    avals = sorted([(a,acodes[a]) for a in acodes])
    for argtype,argsig in avals:
        l = argsig
        if(len(l) == 1):
            continue # These are handled by existing code.
        else:
            l = l[1:]
        print("    case '%s': /* %s */"%(l,argtype))
        print("      //break;")
    print("""
    default:
        as_bad (_(\"bad Crypto ISE field specifier 'X%c'\"), *args);
        break;
    """)
    print("}")
    print("break;")

    # Generate instruction validation logic
    print("")
    print("case 'X': /* SCARV Crypto ISE */ ")
    print("  switch (c = *p++){")

    avals = sorted([(a,acodes[a]) for a in acodes])
    for argtype,argsig in avals:
        l = argsig
        if(len(l) == 1):
            continue # These are handled by existing code.
        else:
            l = l[1:]
        print("    case '%s': used_bits |= ENCODE_X_%s(-1U) ;break;/* %s */"%(
            l, argtype.upper(), argtype)
        )
    print("""
    default:
    as_bad (_("internal: bad RISC-V Crypto opcode (unknown operand type `X%c'): %s %s"),
    c, opc->name, opc->args);
return FALSE;
   }
   break;""")
    


def make_c(match,mask):
  print '/* Automatically generated by parse-opcodes.  */'
  print '#ifndef RISCV_ENCODING_H'
  print '#define RISCV_ENCODING_H'
  for name in namelist:
    name2 = name.upper().replace('.','_')
    print '#define MATCH_%s %s' % (name2, hex(match[name]))
    print '#define MASK_%s  %s' % (name2, hex(mask[name]))

  make_c_extra(match,mask)

def yank(num,start,len):
  return (num >> start) & ((1 << len) - 1)

def str_arg(arg0,name,match,arguments):
  if arg0 in arguments:
    return name or arg0
  else:
    start = arglut[arg0][1]
    len = arglut[arg0][0] - arglut[arg0][1] + 1
    return binary(yank(match,start,len),len)

def str_inst(name,arguments):
  return name.replace('.rv32','').upper()

def print_unimp_type(name,match,arguments):
  print """
&
\\multicolumn{10}{|c|}{%s} & %s \\\\
\\cline{2-11}
  """ % \
  ( \
    '0'*32, \
    'UNIMP' \
  )

def print_u_type(name,match,arguments):
  print """
&
\\multicolumn{8}{|c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} & %s \\\\
\\cline{2-11}
  """ % \
  ( \
    str_arg('imm20','imm[31:12]',match,arguments), \
    str_arg('rd','',match,arguments), \
    binary(yank(match,opcode_base,opcode_size),opcode_size), \
    str_inst(name,arguments) \
  )

def print_uj_type(name,match,arguments):
  print """
&
\\multicolumn{8}{|c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} & %s \\\\
\\cline{2-11}
  """ % \
  ( \
    str_arg('jimm20','imm[20$\\vert$10:1$\\vert$11$\\vert$19:12]',match,arguments), \
    str_arg('rd','',match,arguments), \
    binary(yank(match,opcode_base,opcode_size),opcode_size), \
    str_inst(name,arguments) \
  )

def print_s_type(name,match,arguments):
  print """
&
\\multicolumn{4}{|c|}{%s} &
\\multicolumn{2}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} & %s \\\\
\\cline{2-11}
  """ % \
  ( \
    str_arg('imm12hi','imm[11:5]',match,arguments), \
    str_arg('rs2','',match,arguments), \
    str_arg('rs1','',match,arguments), \
    binary(yank(match,funct_base,funct_size),funct_size), \
    str_arg('imm12lo','imm[4:0]',match,arguments), \
    binary(yank(match,opcode_base,opcode_size),opcode_size), \
    str_inst(name,arguments) \
  )

def print_sb_type(name,match,arguments):
  print """
&
\\multicolumn{4}{|c|}{%s} &
\\multicolumn{2}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} & %s \\\\
\\cline{2-11}
  """ % \
  ( \
    str_arg('bimm12hi','imm[12$\\vert$10:5]',match,arguments), \
    str_arg('rs2','',match,arguments), \
    str_arg('rs1','',match,arguments), \
    binary(yank(match,funct_base,funct_size),funct_size), \
    str_arg('bimm12lo','imm[4:1$\\vert$11]',match,arguments), \
    binary(yank(match,opcode_base,opcode_size),opcode_size), \
    str_inst(name,arguments) \
  )

def print_i_type(name,match,arguments):
  print """
&
\\multicolumn{6}{|c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} & %s \\\\
\\cline{2-11}
  """ % \
  ( \
    str_arg('imm12','imm[11:0]',match,arguments), \
    str_arg('rs1','',match,arguments), \
    binary(yank(match,funct_base,funct_size),funct_size), \
    str_arg('rd','',match,arguments), \
    binary(yank(match,opcode_base,opcode_size),opcode_size), \
    str_inst(name,arguments) \
  )

def print_csr_type(name,match,arguments):
  print """
&
\\multicolumn{6}{|c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} & %s \\\\
\\cline{2-11}
  """ % \
  ( \
    str_arg('imm12','csr',match,arguments), \
    ('zimm' if name[-1] == 'i' else 'rs1'), \
    binary(yank(match,funct_base,funct_size),funct_size), \
    str_arg('rd','',match,arguments), \
    binary(yank(match,opcode_base,opcode_size),opcode_size), \
    str_inst(name,arguments) \
  )

def print_ish_type(name,match,arguments):
  print """
&
\\multicolumn{3}{|c|}{%s} &
\\multicolumn{3}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} & %s \\\\
\\cline{2-11}
  """ % \
  ( \
    binary(yank(match,26,6),6), \
    str_arg('shamt','shamt',match,arguments), \
    str_arg('rs1','',match,arguments), \
    binary(yank(match,funct_base,funct_size),funct_size), \
    str_arg('rd','',match,arguments), \
    binary(yank(match,opcode_base,opcode_size),opcode_size), \
    str_inst(name,arguments) \
  )

def print_ishw_type(name,match,arguments):
  print """
&
\\multicolumn{4}{|c|}{%s} &
\\multicolumn{2}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} & %s \\\\
\\cline{2-11}
  """ % \
  ( \
    binary(yank(match,25,7),7), \
    str_arg('shamtw','shamt',match,arguments), \
    str_arg('rs1','',match,arguments), \
    binary(yank(match,funct_base,funct_size),funct_size), \
    str_arg('rd','',match,arguments), \
    binary(yank(match,opcode_base,opcode_size),opcode_size), \
    str_inst(name,arguments) \
  )

def print_r_type(name,match,arguments):
  print """
&
\\multicolumn{4}{|c|}{%s} &
\\multicolumn{2}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} & %s \\\\
\\cline{2-11}
  """ % \
  ( \
    binary(yank(match,25,7),7), \
    str_arg('rs2','',match,arguments), \
    'zimm' in arguments and str_arg('zimm','imm[4:0]',match,arguments) or str_arg('rs1','',match,arguments), \
    str_arg('rm','',match,arguments), \
    str_arg('rd','',match,arguments), \
    binary(yank(match,opcode_base,opcode_size),opcode_size), \
    str_inst(name,arguments) \
  )

def print_r4_type(name,match,arguments):
  print """
&
\\multicolumn{2}{|c|}{%s} &
\\multicolumn{2}{c|}{%s} &
\\multicolumn{2}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} & %s \\\\
\\cline{2-11}
  """ % \
  ( \
    str_arg('rs3','',match,arguments), \
    binary(yank(match,25,2),2), \
    str_arg('rs2','',match,arguments), \
    str_arg('rs1','',match,arguments), \
    str_arg('rm','',match,arguments), \
    str_arg('rd','',match,arguments), \
    binary(yank(match,opcode_base,opcode_size),opcode_size), \
    str_inst(name,arguments) \
  )

def print_amo_type(name,match,arguments):
  print """
&
\\multicolumn{2}{|c|}{%s} &
\\multicolumn{1}{c|}{aq} &
\\multicolumn{1}{c|}{rl} &
\\multicolumn{2}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} & %s \\\\
\\cline{2-11}
  """ % \
  ( \
    binary(yank(match,27,5),5), \
    str_arg('rs2','',match,arguments), \
    str_arg('rs1','',match,arguments), \
    binary(yank(match,funct_base,funct_size),funct_size), \
    str_arg('rd','',match,arguments), \
    binary(yank(match,opcode_base,opcode_size),opcode_size), \
    str_inst(name,arguments) \
  )

def print_fence_type(name,match,arguments):
  print """
&
\\multicolumn{2}{|c|}{%s} &
\\multicolumn{3}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} &
\\multicolumn{1}{c|}{%s} & %s \\\\
\\cline{2-11}
  """ % \
  ( \
    str_arg('fm','fm',match,arguments), \
    str_arg('pred','pred',match,arguments), \
    str_arg('succ','',match,arguments), \
    str_arg('rs1','',match,arguments), \
    binary(yank(match,funct_base,funct_size),funct_size), \
    str_arg('rd','',match,arguments), \
    binary(yank(match,opcode_base,opcode_size),opcode_size), \
    str_inst(name,arguments) \
  )

def print_header(*types):
  print """
\\newpage

\\begin{table}[p]
\\begin{small}
\\begin{center}
\\begin{tabular}{p{0in}p{0.4in}p{0.05in}p{0.05in}p{0.05in}p{0.05in}p{0.4in}p{0.6in}p{0.4in}p{0.6in}p{0.7in}l}
& & & & & & & & & & \\\\
                      &
\\multicolumn{1}{l}{\\instbit{31}} &
\\multicolumn{1}{r}{\\instbit{27}} &
\\instbit{26} &
\\instbit{25} &
\\multicolumn{1}{l}{\\instbit{24}} &
\\multicolumn{1}{r}{\\instbit{20}} &
\\instbitrange{19}{15} &
\\instbitrange{14}{12} &
\\instbitrange{11}{7} &
\\instbitrange{6}{0} \\\\
\\cline{2-11}
"""
  if 'r' in types:
    print """
&
\\multicolumn{4}{|c|}{funct7} &
\\multicolumn{2}{c|}{rs2} &
\\multicolumn{1}{c|}{rs1} &
\\multicolumn{1}{c|}{funct3} &
\\multicolumn{1}{c|}{rd} &
\\multicolumn{1}{c|}{opcode} & R-type \\\\
\\cline{2-11}
"""
  if 'r4' in types:
    print """
&
\\multicolumn{2}{|c|}{rs3} &
\\multicolumn{2}{c|}{funct2} &
\\multicolumn{2}{c|}{rs2} &
\\multicolumn{1}{c|}{rs1} &
\\multicolumn{1}{c|}{funct3} &
\\multicolumn{1}{c|}{rd} &
\\multicolumn{1}{c|}{opcode} & R4-type \\\\
\\cline{2-11}
  """
  if 'i' in types:
    print """
&
\\multicolumn{6}{|c|}{imm[11:0]} &
\\multicolumn{1}{c|}{rs1} &
\\multicolumn{1}{c|}{funct3} &
\\multicolumn{1}{c|}{rd} &
\\multicolumn{1}{c|}{opcode} & I-type \\\\
\\cline{2-11}
"""
  if 's' in types:
    print """
&
\\multicolumn{4}{|c|}{imm[11:5]} &
\\multicolumn{2}{c|}{rs2} &
\\multicolumn{1}{c|}{rs1} &
\\multicolumn{1}{c|}{funct3} &
\\multicolumn{1}{c|}{imm[4:0]} &
\\multicolumn{1}{c|}{opcode} & S-type \\\\
\\cline{2-11}
"""
  if 'sb' in types:
    print """
&
\\multicolumn{4}{|c|}{imm[12$\\vert$10:5]} &
\\multicolumn{2}{c|}{rs2} &
\\multicolumn{1}{c|}{rs1} &
\\multicolumn{1}{c|}{funct3} &
\\multicolumn{1}{c|}{imm[4:1$\\vert$11]} &
\\multicolumn{1}{c|}{opcode} & B-type \\\\
\\cline{2-11}
"""
  if 'u' in types:
    print """
&
\\multicolumn{8}{|c|}{imm[31:12]} &
\\multicolumn{1}{c|}{rd} &
\\multicolumn{1}{c|}{opcode} & U-type \\\\
\\cline{2-11}
"""
  if 'uj' in types:
    print """
&
\\multicolumn{8}{|c|}{imm[20$\\vert$10:1$\\vert$11$\\vert$19:12]} &
\\multicolumn{1}{c|}{rd} &
\\multicolumn{1}{c|}{opcode} & J-type \\\\
\\cline{2-11}
"""

def print_subtitle(title):
  print """
&
\\multicolumn{10}{c}{} & \\\\
&
\\multicolumn{10}{c}{\\bf %s} & \\\\
\\cline{2-11}
  """ % title

def print_footer(caption=''):
  print """
\\end{tabular}
\\end{center}
\\end{small}
%s
\\label{instr-table}
\\end{table}
  """ % caption

def print_inst(n):
  if n == 'fence' or n == 'fence.i':
    print_fence_type(n, match[n], arguments[n])
  elif 'aqrl' in arguments[n]:
    print_amo_type(n, match[n], arguments[n])
  elif 'shamt' in arguments[n]:
    print_ish_type(n, match[n], arguments[n])
  elif 'shamtw' in arguments[n]:
    print_ishw_type(n, match[n], arguments[n])
  elif 'imm20' in arguments[n]:
    print_u_type(n, match[n], arguments[n])
  elif 'jimm20' in arguments[n]:
    print_uj_type(n, match[n], arguments[n])
  elif n[:3] == 'csr':
    print_csr_type(n, match[n], arguments[n])
  elif 'imm12' in arguments[n] or n == 'ecall' or n == 'ebreak':
    print_i_type(n, match[n], arguments[n])
  elif 'imm12hi' in arguments[n]:
    print_s_type(n, match[n], arguments[n])
  elif 'bimm12hi' in arguments[n]:
    print_sb_type(n, match[n], arguments[n])
  elif 'rs3' in arguments[n]:
    print_r4_type(n, match[n], arguments[n])
  else:
    print_r_type(n, match[n], arguments[n])

def print_insts(*names):
  for n in names:
    print_inst(n)

def make_supervisor_latex_table():
  print_header('i')
  print_subtitle('Environment Call and Breakpoint')
  print_insts('ecall', 'ebreak')
  print_subtitle('Trap-Return Instructions')
  print_insts('uret', 'sret', 'mret')
  print_subtitle('Interrupt-Management Instructions')
  print_insts('wfi')
  print_subtitle('Memory-Management Instructions')
  print_insts('sfence.vma')
  print_footer('\\caption{RISC-V Privileged Instructions}')

def make_latex_table():
  print_header('r','i','s','sb','u','uj')
  print_subtitle('RV32I Base Instruction Set')
  print_insts('lui', 'auipc')
  print_insts('jal', 'jalr', 'beq', 'bne', 'blt', 'bge', 'bltu', 'bgeu')
  print_insts('lb', 'lh', 'lw', 'lbu', 'lhu', 'sb', 'sh', 'sw')
  print_insts('addi', 'slti', 'sltiu', 'xori', 'ori', 'andi', 'slli.rv32', 'srli.rv32', 'srai.rv32')
  print_insts('add', 'sub', 'sll', 'slt', 'sltu', 'xor', 'srl', 'sra', 'or', 'and')
  print_insts('fence', 'fence.i')
  print_insts('ecall', 'ebreak')
  print_insts('csrrw', 'csrrs', 'csrrc')
  print_insts('csrrwi', 'csrrsi', 'csrrci')
  print_footer()

  print_header('r','a','i','s')
  print_subtitle('RV64I Base Instruction Set (in addition to RV32I)')
  print_insts('lwu', 'ld', 'sd')
  print_insts('slli', 'srli', 'srai')
  print_insts('addiw', 'slliw', 'srliw', 'sraiw')
  print_insts('addw', 'subw', 'sllw', 'srlw', 'sraw')
  print_subtitle('RV32M Standard Extension')
  print_insts('mul', 'mulh', 'mulhsu', 'mulhu')
  print_insts('div', 'divu', 'rem', 'remu')
  print_subtitle('RV64M Standard Extension (in addition to RV32M)')
  print_insts('mulw', 'divw', 'divuw', 'remw', 'remuw')
  print_subtitle('RV32A Standard Extension')
  print_insts('lr.w', 'sc.w')
  print_insts('amoswap.w')
  print_insts('amoadd.w', 'amoxor.w', 'amoand.w', 'amoor.w')
  print_insts('amomin.w', 'amomax.w', 'amominu.w', 'amomaxu.w')
  print_footer()

  print_header('r','r4','i','s')
  print_subtitle('RV64A Standard Extension (in addition to RV32A)')
  print_insts('lr.d', 'sc.d')
  print_insts('amoswap.d')
  print_insts('amoadd.d', 'amoxor.d', 'amoand.d', 'amoor.d')
  print_insts('amomin.d', 'amomax.d', 'amominu.d', 'amomaxu.d')
  print_subtitle('RV32F Standard Extension')
  print_insts('flw', 'fsw')
  print_insts('fmadd.s', 'fmsub.s', 'fnmsub.s', 'fnmadd.s')
  print_insts('fadd.s', 'fsub.s', 'fmul.s', 'fdiv.s', 'fsqrt.s')
  print_insts('fsgnj.s', 'fsgnjn.s', 'fsgnjx.s', 'fmin.s', 'fmax.s')
  print_insts('fcvt.w.s', 'fcvt.wu.s', 'fmv.x.w')
  print_insts('feq.s', 'flt.s', 'fle.s', 'fclass.s')
  print_insts('fcvt.s.w', 'fcvt.s.wu', 'fmv.w.x')
  print_footer()

  print_header('r','r4','i','s')
  print_subtitle('RV64F Standard Extension (in addition to RV32F)')
  print_insts('fcvt.l.s', 'fcvt.lu.s')
  print_insts('fcvt.s.l', 'fcvt.s.lu')
  print_subtitle('RV32D Standard Extension')
  print_insts('fld', 'fsd')
  print_insts('fmadd.d', 'fmsub.d', 'fnmsub.d', 'fnmadd.d')
  print_insts('fadd.d', 'fsub.d', 'fmul.d', 'fdiv.d', 'fsqrt.d')
  print_insts('fsgnj.d', 'fsgnjn.d', 'fsgnjx.d', 'fmin.d', 'fmax.d')
  print_insts('fcvt.s.d', 'fcvt.d.s')
  print_insts('feq.d', 'flt.d', 'fle.d', 'fclass.d')
  print_insts('fcvt.w.d', 'fcvt.wu.d')
  print_insts('fcvt.d.w', 'fcvt.d.wu')
  print_subtitle('RV64D Standard Extension (in addition to RV32D)')
  print_insts('fcvt.l.d', 'fcvt.lu.d', 'fmv.x.d')
  print_insts('fcvt.d.l', 'fcvt.d.lu', 'fmv.d.x')
  print_footer('\\caption{Instruction listing for RISC-V}')

def print_chisel_insn(name):
  s = "  def %-18s = BitPat(\"b" % name.replace('.', '_').upper()
  for i in range(31, -1, -1):
    if yank(mask[name], i, 1):
      s = '%s%d' % (s, yank(match[name], i, 1))
    else:
      s = s + '?'
  print s + "\")"

def make_chisel():
  print '/* Automatically generated by parse-opcodes */'
  print 'object Instructions {'
  for name in namelist:
    print_chisel_insn(name)
  print '}'
  print 'object Causes {'
  for num, name in causes:
    print '  val %s = %s' % (name.lower().replace(' ', '_'), hex(num))
  print '  val all = {'
  print '    val res = collection.mutable.ArrayBuffer[Int]()'
  for num, name in causes:
    print '    res += %s' % (name.lower().replace(' ', '_'))
  print '    res.toArray'
  print '  }'
  print '}'
  print 'object CSRs {'
  for num, name in csrs+csrs32:
    print '  val %s = %s' % (name, hex(num))
  print '  val all = {'
  print '    val res = collection.mutable.ArrayBuffer[Int]()'
  for num, name in csrs:
    print '    res += %s' % (name)
  print '    res.toArray'
  print '  }'
  print '  val all32 = {'
  print '    val res = collection.mutable.ArrayBuffer(all:_*)'
  for num, name in csrs32:
    print '    res += %s' % (name)
  print '    res.toArray'
  print '  }'
  print '}'

def signed(value, width):
  if 0 <= value < (1<<(width-1)):
    return value
  else:
    return value - (1<<width)

def print_go_insn(name):
  print '\tcase A%s:' % name.upper().replace('.', '')
  m = match[name]
  opcode = yank(m, 0, 7)
  funct3 = yank(m, 12, 3)
  rs2 = yank(m, 20, 5)
  csr = yank(m, 20, 12)
  funct7 = yank(m, 25, 7)
  print '\t\treturn &inst{0x%x, 0x%x, 0x%x, %d, 0x%x}, true' % (opcode, funct3, rs2, signed(csr, 12), funct7)

def make_go():
  print '// Automatically generated by parse-opcodes'
  print
  print 'package riscv'
  print
  print 'import "cmd/internal/obj"'
  print
  print 'type inst struct {'
  print '\topcode uint32'
  print '\tfunct3 uint32'
  print '\trs2    uint32'
  print '\tcsr    int64'
  print '\tfunct7 uint32'
  print '}'
  print
  print 'func encode(a obj.As) (i *inst, ok bool) {'
  print '\tswitch a {'
  for name in namelist:
    print_go_insn(name)
  print '\t}'
  print '\treturn nil, false'
  print '}'

for line in sys.stdin:
  line = line.partition('#')
  tokens = line[0].split()

  if len(tokens) == 0:
    continue
  assert len(tokens) >= 2

  name = tokens[0]
  pseudo = name[0] == '@'
  if pseudo:
    name = name[1:]
  mymatch = 0
  mymask = 0
  cover = 0

  if not name in arguments.keys():
    arguments[name] = []

  for token in tokens[1:]:
    if len(token.split('=')) == 2:
      tokens = token.split('=')
      if len(tokens[0].split('..')) == 2:
        tmp = tokens[0].split('..')
        hi = int(tmp[0])
        lo = int(tmp[1])
        if hi <= lo:
          sys.exit("%s: bad range %d..%d" % (name,hi,lo))
      else:
        hi = lo = int(tokens[0])

      if tokens[1] != 'ignore':
        val = int(tokens[1], 0)
        if val >= (1 << (hi-lo+1)):
          sys.exit("%s: bad value %d for range %d..%d" % (name,val,hi,lo))
        mymatch = mymatch | (val << lo)
        mymask = mymask | ((1<<(hi+1))-(1<<lo))

      if cover & ((1<<(hi+1))-(1<<lo)):
        sys.exit("%s: overspecified" % name)
      cover = cover | ((1<<(hi+1))-(1<<lo))

    elif token in arglut:
      if cover & ((1<<(arglut[token][0]+1))-(1<<arglut[token][1])):
        sys.exit("%s: overspecified" % name)
      cover = cover | ((1<<(arglut[token][0]+1))-(1<<arglut[token][1]))
      arguments[name].append(token)

    else:
      sys.exit("%s: unknown token %s" % (name,token))

  if not (cover == 0xFFFFFFFF or cover == 0xFFFF):
    sys.exit("%s: not all bits are covered: %s" % (name, bin(cover)))

  if pseudo:
    pseudos[name] = 1
  else:
    for name2,match2 in match.iteritems():
      if name2 not in pseudos and (match2 & mymask) == mymatch:
        sys.exit("%s and %s overlap" % (name,name2))

  mask[name] = mymask
  match[name] = mymatch
  namelist.append(name)

if sys.argv[1] == '-tex':
  make_latex_table()
elif sys.argv[1] == '-privtex':
  make_supervisor_latex_table()
elif sys.argv[1] == '-chisel':
  make_chisel()
elif sys.argv[1] == '-c':
  make_c(match,mask)
elif sys.argv[1] == '-go':
  make_go()
else:
  assert 0
